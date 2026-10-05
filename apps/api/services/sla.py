"""Proof-video SLA (PRD §6): one number per event drives the badge, the copy and this board."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Booking, BookingStatus, PujaEvent
from services import notify, site_config
from services.alerts import ops_alert
from services.catalog import puja_title
from services.i18n import fmt_dt_ist, utcnow

S = BookingStatus
OPEN = [S.confirmed, S.locked, S.performed, S.proof_ready]
AT_RISK_WINDOW = timedelta(hours=6)


def due_at(ev: PujaEvent):
    return ev.starts_at + timedelta(hours=ev.video_sla_hours)


async def board(db: AsyncSession) -> dict:
    now = utcnow()
    refund_days = await site_config.get(db, "proof_refund_after_days")
    rows = (await db.execute(
        select(Booking, PujaEvent).join(PujaEvent, Booking.puja_event_id == PujaEvent.id)
        .where(Booking.status.in_(OPEN), PujaEvent.starts_at < now + timedelta(days=1))
    )).all()
    groups: dict[int, dict] = {}
    for b, ev in rows:
        due = due_at(ev)
        if now < due - AT_RISK_WINDOW:
            continue
        state = "breached" if now >= due else "at_risk"
        g = groups.setdefault(ev.id, {"event_id": ev.id, "puja_id": ev.puja_id,
                                      "title": await puja_title(db, ev.puja_id, "en"),
                                      "starts_at": ev.starts_at.isoformat(), "due_at": due.isoformat(),
                                      "event_status": ev.status.value, "bookings": []})
        g["bookings"].append({"id": str(b.id), "code": b.code, "status": b.status.value, "state": state,
                              "refund_due": now >= due + timedelta(days=refund_days),
                              "delay_notified": b.sla_breach_notified_at is not None})
    out = list(groups.values())
    out.sort(key=lambda g: g["due_at"])
    return {"groups": out, "as_of": now.isoformat()}


async def check_breaches(db: AsyncSession) -> int:
    """Alerts ops and sends `proof_delayed` once per breached booking. Never fails silently."""
    now = utcnow()
    eta_h = await site_config.get(db, "proof_delay_eta_hours")
    rows = (await db.execute(
        select(Booking, PujaEvent).join(PujaEvent, Booking.puja_event_id == PujaEvent.id)
        .where(Booking.status.in_(OPEN), Booking.sla_breach_notified_at.is_(None), PujaEvent.starts_at < now)
    )).all()
    breached: dict[int, list[Booking]] = {}
    for b, ev in rows:
        if now >= due_at(ev):
            breached.setdefault(ev.id, []).append(b)
    for ev_id, bookings in breached.items():
        ev = await db.get(PujaEvent, ev_id)
        title = await puja_title(db, ev.puja_id, "en")
        await ops_alert("Proof video SLA breached",
                        f"{title} ({fmt_dt_ist(ev.starts_at, 'en')}): {len(bookings)} bookings past their "
                        f"{ev.video_sla_hours} h SLA.", event_id=ev_id)
        new_eta = now + timedelta(hours=eta_h)
        for b in bookings:
            b.sla_breach_notified_at = now
            await notify.queue(db, template_key="proof_delayed", to=b.whatsapp_e164, locale=b.locale, booking=b,
                               occurrence_key="breach:1",
                               params=[await puja_title(db, ev.puja_id, b.locale), fmt_dt_ist(new_eta, b.locale)])
    return sum(len(v) for v in breached.values())
