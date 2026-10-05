"""Puja events — cutoff locking, sankalp sheet, started/performed, disruptions (PRD §6)."""

import logging
import re
from datetime import datetime, timedelta

from dateutil.rrule import rrulestr
from indic_transliteration import sanscript
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logging_setup import log
from models import Booking, BookingStatus, EventStatus, Puja, PujaEvent
from providers.media.storage import put_file
from services import bookings as booking_svc
from services import notify, site_config
from services.audit import audit
from services.catalog import puja_title, temple_name
from services.i18n import IST, fmt_date, utcnow

logger = logging.getLogger("events")
S = BookingStatus

_SCRIPT_FOR_LANGUAGE = {
    "sanskrit": sanscript.DEVANAGARI, "hindi": sanscript.DEVANAGARI, "marathi": sanscript.DEVANAGARI,
    "telugu": sanscript.TELUGU, "tamil": sanscript.TAMIL, "kannada": sanscript.KANNADA,
    "malayalam": sanscript.MALAYALAM,
}
_INDIC_RANGES = [(0x0900, 0x097F, sanscript.DEVANAGARI), (0x0C00, 0x0C7F, sanscript.TELUGU),
                 (0x0B80, 0x0BFF, sanscript.TAMIL), (0x0C80, 0x0CFF, sanscript.KANNADA),
                 (0x0D00, 0x0D7F, sanscript.MALAYALAM)]


def _source_scheme(text: str) -> str:
    for ch in text:
        for lo, hi, scheme in _INDIC_RANGES:
            if lo <= ord(ch) <= hi:
                return scheme
    return sanscript.ITRANS


def transliterate(text: str | None, sankalp_language: str) -> str:
    """Best-effort transliteration of a name into the sankalp script. The sheet always shows the original too."""
    if not text:
        return ""
    target = _SCRIPT_FOR_LANGUAGE.get(sankalp_language.strip().lower())
    if target is None:
        return text
    src = _source_scheme(text)
    if src == target:
        return text
    if src == sanscript.ITRANS:
        text = re.sub(r"[^A-Za-z\s.'-]", "", text).lower()
        text = re.sub(r"ee", "ii", text)
        text = re.sub(r"oo", "uu", text)
    out = sanscript.transliterate(text, src, target)
    if target == sanscript.DEVANAGARI:  # Hindi/Sanskrit names drop the trailing virama
        out = re.sub("्(?=\\s|$)", "", out)
    return out


async def sheet_rows(db: AsyncSession, ev: PujaEvent) -> list[dict]:
    puja = ev.puja or await db.get(Puja, ev.puja_id)
    lang = puja.sankalp_language
    gotra_fallback = await site_config.get(db, "gotra_fallback")
    rows = (await db.execute(
        select(Booking).where(Booking.puja_event_id == ev.id, Booking.sheet_position.is_not(None),
                              Booking.status.not_in([S.cancelled, S.refunded, S.rescheduled]))
        .order_by(Booking.sheet_position)
    )).scalars().all()
    out = []
    for b in rows:
        fallback = gotra_fallback.get(b.locale) or gotra_fallback.get("en", "")
        out.append({
            "position": b.sheet_position, "booking_id": str(b.id), "code": b.code, "status": b.status.value,
            "wish": b.wish, "wish_sankalp": b.wish,
            "names": [{
                "name": n.name, "name_sankalp": transliterate(n.name, lang), "relation": n.relation,
                "gotra": n.gotra if not n.gotra_unknown else fallback,
                "gotra_sankalp": transliterate(n.gotra if not n.gotra_unknown else fallback, lang),
                "gotra_unknown": n.gotra_unknown, "nakshatra": n.nakshatra,
            } for n in b.names],
        })
    return out


async def lock_due_events(db: AsyncSession) -> list[int]:
    """At cutoff: freeze names, number the sheet, render the PDF."""
    due = (await db.execute(select(PujaEvent).where(
        PujaEvent.booking_cutoff_at <= utcnow(), PujaEvent.locked_at.is_(None),
        PujaEvent.status == EventStatus.scheduled,
    ))).scalars().all()
    locked = []
    for ev in due:
        # Unanswered reschedules default to Accept.
        for b in (await db.execute(select(Booking).where(Booking.puja_event_id == ev.id,
                                                         Booking.status == S.rescheduled))).scalars():
            await booking_svc.answer_reschedule(db, b, accept=True)
        bookings = (await db.execute(
            select(Booking).where(Booking.puja_event_id == ev.id, Booking.status == S.confirmed)
            .order_by(Booking.confirmed_at, Booking.created_at)
        )).scalars().all()
        for i, b in enumerate(bookings, start=1):
            await booking_svc.transition(db, b, S.locked)
            b.sheet_position = i
        ev.locked_at = utcnow()
        await db.flush()
        await render_sheet(db, ev)
        locked.append(ev.id)
        log(logger, "event locked", event_id=ev.id, bookings=len(bookings))
    return locked


async def append_to_sheet(db: AsyncSession, ev: PujaEvent, b: Booking) -> None:
    if b.sheet_position is None:
        last = (await db.execute(select(func.max(Booking.sheet_position)).where(Booking.puja_event_id == ev.id))
                ).scalar() or 0
        b.sheet_position = last + 1
    await db.flush()
    await render_sheet(db, ev)


async def render_sheet(db: AsyncSession, ev: PujaEvent) -> str:
    from services.pdf import sankalp_sheet_pdf

    puja = ev.puja or await db.get(Puja, ev.puja_id)
    title = await puja_title(db, puja.id, "en")
    temple = await temple_name(db, puja.temple_id, "en")
    rows = await sheet_rows(db, ev)
    path = sankalp_sheet_pdf(title=title, temple=temple, starts_at=ev.starts_at, language=puja.sankalp_language,
                             rows=rows)
    key = f"sheets/event-{ev.id}-{int(utcnow().timestamp())}.pdf"
    put_file(path, key, "application/pdf")
    ev.sankalp_sheet_key = key
    return key


async def mark_started(db: AsyncSession, ev: PujaEvent, staff_id: int) -> int:
    if ev.status not in (EventStatus.scheduled, EventStatus.started):
        raise booking_svc.BookingError("bad_event_state")
    if ev.locked_at is None:
        await lock_now(db, ev)
    ev.status = EventStatus.started
    await audit(db, staff_id, "event.started", "puja_event", ev.id)
    n = 0
    for b in (await db.execute(select(Booking).where(Booking.puja_event_id == ev.id,
                                                     Booking.status == S.locked))).scalars():
        await notify.queue(db, template_key="puja_started", to=b.whatsapp_e164, locale=b.locale, booking=b,
                           occurrence_key=f"event:{ev.id}",
                           params=[await puja_title(db, ev.puja_id, b.locale),
                                   await temple_name(db, ev.puja.temple_id, b.locale)])
        n += 1
    return n


async def lock_now(db: AsyncSession, ev: PujaEvent) -> None:
    """Ops can start an event before its cutoff job ran (e.g. worker lag); lock it the same way."""
    ev.booking_cutoff_at = min(ev.booking_cutoff_at, utcnow())
    await db.flush()
    await lock_due_events(db)


async def mark_performed(db: AsyncSession, ev: PujaEvent, staff_id: int) -> int:
    if ev.status not in (EventStatus.started, EventStatus.scheduled):
        raise booking_svc.BookingError("bad_event_state")
    if ev.locked_at is None:
        await lock_now(db, ev)
    ev.status = EventStatus.performed
    await audit(db, staff_id, "event.performed", "puja_event", ev.id)
    n = 0
    for b in (await db.execute(select(Booking).where(Booking.puja_event_id == ev.id,
                                                     Booking.status == S.locked))).scalars():
        await booking_svc.transition(db, b, S.performed)
        n += 1
    return n


async def disrupt(db: AsyncSession, ev: PujaEvent, *, action: str, staff_id: int,
                  new_starts_at: datetime | None = None) -> dict:
    if ev.status in (EventStatus.performed, EventStatus.cancelled, EventStatus.disrupted):
        raise booking_svc.BookingError("bad_event_state")
    affected = (await db.execute(select(Booking).where(
        Booking.puja_event_id == ev.id, Booking.status.in_([S.confirmed, S.locked])
    ))).scalars().all()
    await audit(db, staff_id, "event.disrupted", "puja_event", ev.id,
                {"action": action, "new_starts_at": new_starts_at, "bookings": len(affected)})
    ev.disrupted_action = action
    if action == "refund":
        ev.status = EventStatus.cancelled
        for b in affected:
            await booking_svc.cancel(db, b, reason="event_cancelled", staff_id=staff_id)
        return {"refunded": len(affected)}

    if new_starts_at is None or new_starts_at <= utcnow():
        raise booking_svc.BookingError("bad_new_date")
    cutoff_h = await site_config.get(db, "booking_cutoff_hours_default")
    new = PujaEvent(puja_id=ev.puja_id, starts_at=new_starts_at,
                    booking_cutoff_at=new_starts_at - timedelta(hours=cutoff_h), video_sla_hours=ev.video_sla_hours)
    db.add(new)
    await db.flush()
    ev.status = EventStatus.disrupted
    ev.rescheduled_to_event_id = new.id
    reply_h = await site_config.get(db, "reschedule_reply_hours")
    for b in affected:
        await booking_svc.transition(db, b, S.rescheduled, staff_id=staff_id)
        await notify.cancel_queued(db, b.id, ["puja_reminder"])
        b.reschedule_from_event_id = ev.id
        b.puja_event_id = new.id
        b.sheet_position = None
        b.reschedule_deadline_at = utcnow() + timedelta(hours=reply_h)
        await notify.queue(db, template_key="puja_rescheduled", to=b.whatsapp_e164, locale=b.locale, booking=b,
                           occurrence_key=f"event:{ev.id}",
                           params=[await puja_title(db, ev.puja_id, b.locale), fmt_date(ev.starts_at, b.locale),
                                   fmt_date(new_starts_at, b.locale)],
                           button_params=["accept", "refund"])
    return {"rescheduled": len(affected), "new_event_id": new.id}


async def auto_accept_reschedules(db: AsyncSession) -> int:
    rows = (await db.execute(select(Booking).where(
        Booking.status == S.rescheduled, Booking.reschedule_deadline_at <= utcnow()
    ))).scalars().all()
    for b in rows:
        await booking_svc.answer_reschedule(db, b, accept=True)
    return len(rows)


async def generate_series(db: AsyncSession, *, puja_id: int, rrule: str, first_start_ist: datetime, count: int,
                          video_sla_hours: int | None, cutoff_hours: int | None) -> list[PujaEvent]:
    """Creates one event per occurrence of an RFC 5545 rule (e.g. FREQ=WEEKLY;BYDAY=TU)."""
    if first_start_ist.tzinfo is None:
        first_start_ist = first_start_ist.replace(tzinfo=IST)
    rule = rrulestr(rrule, dtstart=first_start_ist)
    sla_default = await site_config.get(db, "video_sla_hours_default")
    cutoff_default = await site_config.get(db, "booking_cutoff_hours_default")
    puja = await db.get(Puja, puja_id)
    out = []
    for i, dt in enumerate(rule):
        if i >= count:
            break
        ev = PujaEvent(puja_id=puja_id, starts_at=dt,
                       booking_cutoff_at=dt - timedelta(hours=cutoff_hours or cutoff_default),
                       video_sla_hours=video_sla_hours or puja.video_sla_hours or sla_default)
        db.add(ev)
        out.append(ev)
    await db.flush()
    return out
