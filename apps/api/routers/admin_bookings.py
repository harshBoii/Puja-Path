"""Support: booking lookup, timeline, resend, edit names, cancel/refund, notes, assisted booking (PRD §10.6-7)."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from deps import require_role
from models import (
    Booking,
    BookingName,
    BookingNote,
    BookingStatus,
    CallbackRequest,
    MessageLog,
    MessageStatus,
    Package,
    Payment,
    PujaEvent,
    Refund,
    StaffRole,
    StaffUser,
    User,
)
from services import bookings as booking_svc
from services import notify, site_config
from services.audit import audit
from services.catalog import package_label, puja_title, temple_name
from services.i18n import LOCALES, fmt_dt_ist, fmt_money, utcnow

router = APIRouter(prefix="/v1/admin", tags=["admin"])
support = require_role(StaffRole.support_agent, StaffRole.ops_coordinator, StaffRole.finance)
agent = require_role(StaffRole.support_agent)
S = BookingStatus


@router.get("/bookings")
async def search(q: str = "", status: str | None = None, event_id: int | None = None, call_queue: bool = False,
                 db: AsyncSession = Depends(get_db), _: StaffUser = Depends(support)):
    stmt = select(Booking).where(Booking.status != S.draft)
    q = q.strip()
    if q:
        like = f"%{q}%"
        sub = select(BookingName.booking_id).where(BookingName.name.ilike(like))
        stmt = stmt.where(or_(Booking.code == q.upper(), Booking.whatsapp_e164.ilike(like), Booking.id.in_(sub)))
    if status:
        stmt = stmt.where(Booking.status == status)
    if event_id:
        stmt = stmt.where(Booking.puja_event_id == event_id)
    if call_queue:
        stmt = stmt.where(Booking.needs_call_reason.is_not(None))
    rows = (await db.execute(stmt.order_by(Booking.created_at.desc()).limit(100))).scalars().all()
    return [{"id": str(b.id), "code": b.code, "status": b.status.value, "phone": b.whatsapp_e164,
             "name": b.names[0].name if b.names else None, "title": await puja_title(db, b.event.puja_id, "en"),
             "starts_at": b.event.starts_at.isoformat(), "total_minor": b.total_minor, "currency": b.currency,
             "needs_call_reason": b.needs_call_reason} for b in rows]


@router.get("/bookings/{booking_id}")
async def detail(booking_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(support)):
    b = await db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "not_found")
    ev = b.event
    payments = (await db.execute(select(Payment).where(or_(
        Payment.booking_id == b.id,
        (Payment.subscription_id == b.subscription_id) & Payment.booking_id.is_(None) if b.subscription_id else False,
    )).order_by(Payment.created_at))).scalars().all()
    refunds = (await db.execute(select(Refund).where(Refund.booking_id == b.id))).scalars().all()
    messages = (await db.execute(select(MessageLog).where(MessageLog.booking_id == b.id)
                                 .order_by(MessageLog.created_at))).scalars().all()
    notes = (await db.execute(select(BookingNote, StaffUser).join(StaffUser, BookingNote.staff_id == StaffUser.id)
                              .where(BookingNote.booking_id == b.id).order_by(BookingNote.created_at))).all()
    shipment = await booking_svc.get_shipment(db, b.id)
    user = await db.get(User, b.user_id) if b.user_id else None
    return {
        "id": str(b.id), "code": b.code, "status": b.status.value, "locale": b.locale, "currency": b.currency,
        "title": await puja_title(db, ev.puja_id, "en"), "temple": await temple_name(db, ev.puja.temple_id, "en"),
        "event": {"id": ev.id, "starts_at": ev.starts_at.isoformat(), "cutoff": ev.booking_cutoff_at.isoformat(),
                  "status": ev.status.value},
        "package": package_label(b.package.code.value, "en"), "max_names": b.package.max_names,
        "names": [{"name": n.name, "relation": n.relation, "gotra": n.gotra, "gotra_unknown": n.gotra_unknown,
                   "nakshatra": n.nakshatra} for n in b.names],
        "wish": b.wish, "phone": b.whatsapp_e164, "user": {"id": str(user.id), "name": user.name} if user else None,
        "pricing": {"subtotal": b.subtotal_minor, "addons": b.addons_minor, "shipping": b.shipping_minor,
                    "dakshina": b.dakshina_minor, "tax": b.tax_minor, "total": b.total_minor},
        "timestamps": {k: (getattr(b, k).isoformat() if getattr(b, k) else None)
                       for k in ("created_at", "confirmed_at", "performed_at", "proof_sent_at", "completed_at",
                                 "cancelled_at")},
        "cancel_reason": b.cancel_reason, "needs_call_reason": b.needs_call_reason,
        "before_cutoff": ev.booking_cutoff_at > utcnow(),
        "payments": [{"id": str(p.id), "provider": p.provider, "order_id": p.provider_order_id,
                      "payment_id": p.provider_payment_id, "amount_minor": p.amount_minor, "status": p.status}
                     for p in payments],
        "refunds": [{"id": str(r.id), "amount_minor": r.amount_minor, "reason": r.reason, "status": r.status,
                     "provider_refund_id": r.provider_refund_id} for r in refunds],
        "shipment": {"status": shipment.status.value, "awb": shipment.awb, "courier": shipment.courier,
                     "address": shipment.address, "events": shipment.events} if shipment else None,
        "messages": [{"id": str(m.id), "template": m.template_key, "status": m.status.value,
                      "error": m.error_code, "scheduled_for": m.scheduled_for.isoformat() if m.scheduled_for else None,
                      "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                      "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
                      "read_at": m.read_at.isoformat() if m.read_at else None, "provider": m.provider}
                     for m in messages],
        "notes": [{"text": n.text, "by": s.name, "at": n.created_at.isoformat()} for n, s in notes],
        "proof_path": booking_svc.proof_path(b),
    }


@router.post("/messages/{message_id}/resend")
async def resend(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(agent)):
    m = await db.get(MessageLog, message_id)
    if m is None or m.booking_id is None:
        raise HTTPException(404, "not_found")
    b = await db.get(Booking, m.booking_id)
    # A resend is a new occurrence, so the idempotency key still blocks accidental double sends.
    n = (await db.execute(select(MessageLog).where(MessageLog.booking_id == b.id,
                                                   MessageLog.template_key == m.template_key))).scalars().all()
    await notify.queue(db, template_key=m.template_key, to=b.whatsapp_e164, locale=m.locale, booking=b,
                       params=m.params, button_params=m.button_params, header_media_url=m.header_media_url,
                       occurrence_key=f"{m.occurrence_key}#resend{len(n)}")
    await audit(db, staff.id, "message.resend", "booking", b.id, {"template": m.template_key})
    await notify.commit_and_dispatch(db)
    return {"ok": True}


class NamesIn(BaseModel):
    names: list[dict]
    reason: str | None = Field(default=None, max_length=300)


@router.put("/bookings/{booking_id}/names")
async def edit_names(booking_id: uuid.UUID, body: NamesIn, db: AsyncSession = Depends(get_db),
                     staff: StaffUser = Depends(agent)):
    b = await db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "not_found")
    after_cutoff = b.event.booking_cutoff_at <= utcnow()
    if after_cutoff and not body.reason:
        raise HTTPException(400, "reason_required_after_cutoff")
    if not body.names or len(body.names) > b.package.max_names or any(not (n.get("name") or "").strip()
                                                                     for n in body.names):
        raise HTTPException(400, "bad_names")
    before = [{"name": n.name, "gotra": n.gotra} for n in b.names]
    await db.execute(delete(BookingName).where(BookingName.booking_id == b.id))
    b.names = [BookingName(booking_id=b.id, position=i, name=n["name"].strip(), relation=n.get("relation"),
                           gotra=n.get("gotra"), gotra_unknown=bool(n.get("gotra_unknown")),
                           nakshatra=n.get("nakshatra")) for i, n in enumerate(body.names, start=1)]
    await audit(db, staff.id, "booking.edit_names", "booking", b.id,
                {"before": before, "after": body.names, "reason": body.reason, "after_cutoff": after_cutoff})
    await db.flush()
    if after_cutoff and b.event.locked_at:
        from services.events import render_sheet

        await render_sheet(db, b.event)
    await db.commit()
    return {"ok": True}


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=120)
    refund_minor: int | None = Field(default=None, ge=0)


@router.post("/bookings/{booking_id}/cancel")
async def cancel(booking_id: uuid.UUID, body: CancelIn, db: AsyncSession = Depends(get_db),
                 staff: StaffUser = Depends(require_role(StaffRole.support_agent, StaffRole.finance))):
    b = await db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "not_found")
    try:
        await booking_svc.cancel(db, b, reason=body.reason, staff_id=staff.id, refund_minor=body.refund_minor)
    except booking_svc.BookingError as e:
        raise HTTPException(409, e.code) from e
    await notify.commit_and_dispatch(db)
    return {"status": b.status.value}


class PartialRefundIn(BaseModel):
    amount_minor: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=120)


@router.post("/bookings/{booking_id}/refund")
async def partial_refund(booking_id: uuid.UUID, body: PartialRefundIn, db: AsyncSession = Depends(get_db),
                         staff: StaffUser = Depends(require_role(StaffRole.finance, StaffRole.support_agent))):
    """Partial refunds, e.g. add-ons we could not ship, or proof not delivered within 7 days of SLA."""
    b = await db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "not_found")
    r = await booking_svc.refund_booking(db, b, body.amount_minor, body.reason)
    if r is None:
        raise HTTPException(409, "nothing_to_refund")
    await audit(db, staff.id, "booking.refund", "booking", b.id, body.model_dump())
    await notify.commit_and_dispatch(db)
    return {"refund_id": str(r.id), "amount_minor": r.amount_minor}


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/bookings/{booking_id}/notes", status_code=201)
async def add_note(booking_id: uuid.UUID, body: NoteIn, db: AsyncSession = Depends(get_db),
                   staff: StaffUser = Depends(support)):
    db.add(BookingNote(booking_id=booking_id, staff_id=staff.id, text=body.text))
    await audit(db, staff.id, "booking.note", "booking", booking_id, body.model_dump())
    await db.commit()
    return {"ok": True}


@router.post("/bookings/{booking_id}/clear-call-queue")
async def clear_call(booking_id: uuid.UUID, body: NoteIn, db: AsyncSession = Depends(get_db),
                     staff: StaffUser = Depends(agent)):
    b = await db.get(Booking, booking_id)
    if b is None:
        raise HTTPException(404, "not_found")
    b.needs_call_reason = None
    db.add(BookingNote(booking_id=b.id, staff_id=staff.id, text=f"Call queue cleared: {body.text}"))
    await audit(db, staff.id, "booking.call_cleared", "booking", b.id, body.model_dump())
    await db.commit()
    return {"ok": True}


class AssistedIn(BaseModel):
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    event_id: int
    package_id: int
    locale: str = "en"
    currency: str = Field(default="INR", pattern="^(INR|USD)$")
    names: list[dict] = Field(min_length=1)
    wish: str | None = Field(default=None, max_length=140)
    whatsapp_consent_confirmed: bool  # agent confirms the devotee agreed to WhatsApp updates on the call


@router.post("/assisted-bookings", status_code=201)
async def assisted(body: AssistedIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(agent)):
    if not body.whatsapp_consent_confirmed:
        raise HTTPException(400, "consent_required")
    ev = await db.get(PujaEvent, body.event_id)
    pkg = await db.get(Package, body.package_id)
    if ev is None or pkg is None:
        raise HTTPException(404, "not_found")
    if len(body.names) > pkg.max_names:
        raise HTTPException(400, "too_many_names")
    user = (await db.execute(select(User).where(User.phone_e164 == body.phone_e164))).scalar_one_or_none()
    if user is None:
        user = User(phone_e164=body.phone_e164, locale=body.locale if body.locale in LOCALES else "en")
        db.add(user)
        await db.flush()
    try:
        b = await booking_svc.create_draft(db, event=ev, package=pkg, locale=user.locale, currency=body.currency,
                                           user=user)
    except booking_svc.BookingError as e:
        raise HTTPException(409, e.code) from e
    b.assisted_by_staff_id = staff.id
    b.wish = body.wish
    b.consent_whatsapp_at = utcnow()
    b.consent_text_version = f"{await site_config.get(db, 'consent_text_version')}:assisted"
    b.names = [BookingName(booking_id=b.id, position=i, name=n["name"].strip(), relation=n.get("relation"),
                           gotra=n.get("gotra"), gotra_unknown=bool(n.get("gotra_unknown")),
                           nakshatra=n.get("nakshatra")) for i, n in enumerate(body.names, start=1)]
    await booking_svc.reprice(db, b)
    expiry = min(ev.booking_cutoff_at, utcnow() + timedelta(hours=24))
    await notify.queue(db, template_key="payment_link", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       params=[b.names[0].name, await puja_title(db, ev.puja_id, b.locale),
                               fmt_money(b.total_minor, b.currency, b.locale), fmt_dt_ist(expiry, b.locale)],
                       button_params=[f"{b.locale}/checkout/{b.id}"])
    await audit(db, staff.id, "booking.assisted_create", "booking", b.id, body.model_dump())
    await notify.commit_and_dispatch(db)
    return {"id": str(b.id), "code": b.code, "pay_path": f"/{b.locale}/checkout/{b.id}", "total_minor": b.total_minor}


@router.get("/callback-requests")
async def callbacks(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(agent)):
    rows = (await db.execute(select(CallbackRequest).order_by(CallbackRequest.created_at.desc()).limit(200))).scalars()
    return [{"id": r.id, "phone": r.phone_e164, "name": r.name, "puja_id": r.puja_id, "locale": r.locale,
             "handled": r.handled_at is not None, "at": r.created_at.isoformat()} for r in rows]


@router.post("/callback-requests/{req_id}/handled")
async def callback_handled(req_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(agent)):
    r = await db.get(CallbackRequest, req_id)
    if r is None:
        raise HTTPException(404, "not_found")
    r.handled_at = utcnow()
    await audit(db, staff.id, "callback.handled", "callback_request", req_id)
    await db.commit()
    return {"ok": True}


@router.get("/messages/stats")
async def message_stats(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(support)):
    from sqlalchemy import func

    rows = (await db.execute(select(MessageLog.template_key, MessageLog.status, func.count())
                             .where(MessageLog.created_at > utcnow() - timedelta(days=30))
                             .group_by(MessageLog.template_key, MessageLog.status))).all()
    out: dict[str, dict] = {}
    for key, status, n in rows:
        out.setdefault(key, {s.value: 0 for s in MessageStatus})[status.value] = n
    for v in out.values():
        sent = v["sent"] + v["delivered"] + v["read"]
        v["delivery_rate"] = round((v["delivered"] + v["read"]) / sent, 3) if sent else None
        v["read_rate"] = round(v["read"] / sent, 3) if sent else None
    return out
