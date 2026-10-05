"""Booking lifecycle — PRD §6 state machine, §8 payments/refunds.

Every transition goes through `transition()`; side effects (WhatsApp templates) are queued in the same
transaction, so a rolled-back transition never sends a message.
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from logging_setup import log
from models import (
    AddonItem,
    Booking,
    BookingStatus,
    Mandate,
    Package,
    Payment,
    PaymentMode,
    Puja,
    PujaEvent,
    Refund,
    Shipment,
    ShipmentStatus,
    Subscription,
    SubscriptionStatus,
    User,
)
from providers.payments import get_payment_provider
from providers.payments.base import Customer, PaymentEvent
from security import booking_code, proof_token
from services import notify, site_config
from services.audit import audit
from services.catalog import package_label, puja_title, temple_name
from services.i18n import fmt_date, fmt_dt_ist, fmt_money, reminder_time, tz_for_phone, utcnow

logger = logging.getLogger("bookings")
S = BookingStatus

ALLOWED: dict[BookingStatus, set[BookingStatus]] = {
    S.draft: {S.pending_payment, S.cancelled},
    S.pending_payment: {S.confirmed, S.cancelled, S.pending_payment},
    S.confirmed: {S.locked, S.cancelled, S.rescheduled},
    S.locked: {S.performed, S.cancelled, S.rescheduled},
    S.performed: {S.proof_ready},
    S.proof_ready: {S.proof_sent},
    S.proof_sent: {S.completed},
    S.rescheduled: {S.confirmed, S.locked, S.cancelled},
    S.cancelled: {S.refunded},
    S.completed: set(),
    S.refunded: set(),
}

PAYMENT_TTL = timedelta(minutes=30)


class BookingError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


async def transition(db: AsyncSession, b: Booking, to: BookingStatus, *, staff_id: int | None = None,
                     reason: str | None = None) -> None:
    if to not in ALLOWED[b.status]:
        raise BookingError("invalid_transition", f"{b.status.value} -> {to.value}")
    frm = b.status
    b.status = to
    now = utcnow()
    if to == S.confirmed and not b.confirmed_at:
        b.confirmed_at = now
    if to == S.cancelled:
        b.cancelled_at, b.cancel_reason = now, reason
    if to == S.performed:
        b.performed_at = now
    if to == S.proof_sent:
        b.proof_sent_at = now
    if to == S.completed:
        b.completed_at = now
    if staff_id:
        await audit(db, staff_id, "booking.transition", "booking", b.id, {"from": frm, "to": to, "reason": reason})
    log(logger, "booking transition", booking_id=str(b.id), code=b.code, frm=frm.value, to=to.value, reason=reason)


# ------------------------------------------------------------------ context for templates
async def ctx(db: AsyncSession, b: Booking) -> dict:
    ev = b.event or await db.get(PujaEvent, b.puja_event_id)
    puja = ev.puja or await db.get(Puja, ev.puja_id)
    user = await db.get(User, b.user_id) if b.user_id else None
    first = b.names[0].name if b.names else (user.name if user else "")
    return {
        "name": first or "",
        "puja": await puja_title(db, puja.id, b.locale),
        "temple": await temple_name(db, puja.temple_id, b.locale),
        "datetime_ist": fmt_dt_ist(ev.starts_at, b.locale),
        "date": fmt_date(ev.starts_at, b.locale),
        "package": package_label(b.package.code.value if b.package else "individual", b.locale),
        "code": b.code,
        "event": ev,
        "puja_obj": puja,
        "user": user,
    }


def booking_path(b: Booking) -> str:
    return f"{b.locale}/account/bookings/{b.id}"


def proof_path(b: Booking) -> str:
    return f"{b.locale}/proof/{b.proof_token}"


# ------------------------------------------------------------------ drafts + pricing
async def new_booking_code(db: AsyncSession) -> str:
    for _ in range(10):
        code = booking_code()
        exists = (await db.execute(select(Booking.id).where(Booking.code == code))).first()
        if not exists:
            return code
    raise BookingError("code_exhausted")


async def create_draft(db: AsyncSession, *, event: PujaEvent, package: Package, locale: str, currency: str,
                       user: User | None) -> Booking:
    if event.booking_cutoff_at <= utcnow() or event.status.value != "scheduled":
        raise BookingError("event_closed")
    if package.puja_id != event.puja_id or not package.active:
        raise BookingError("bad_package")
    b = Booking(
        code=await new_booking_code(db), user_id=user.id if user else None, puja_event_id=event.id,
        package_id=package.id, locale=locale, currency=currency, status=S.draft, proof_token=proof_token(),
        whatsapp_e164=user.phone_e164 if user else None,
    )
    db.add(b)
    await db.flush()
    b = await reload(db, b.id)
    await reprice(db, b)
    return b


async def reload(db: AsyncSession, booking_id) -> Booking:
    """Fully loads a booking with its relationships (async sessions cannot lazy-load)."""
    return (await db.execute(select(Booking).where(Booking.id == booking_id)
                             .execution_options(populate_existing=True))).scalar_one()


async def reprice(db: AsyncSession, b: Booking, *, occurrences: int = 1) -> dict:
    """Server-side pricing; client-sent prices are never used (PRD §8)."""
    cfg = await site_config.get_all(db)
    pkg = b.package or await db.get(Package, b.package_id)
    cur = b.currency
    subtotal = pkg.price_usd_minor if cur == "USD" else pkg.price_inr_minor
    addons = 0
    for ba in b.addons:
        item = ba.item or await db.get(AddonItem, ba.addon_item_id)
        ba.unit_price_minor = item.price_usd_minor if cur == "USD" else item.price_inr_minor
        addons += ba.qty * ba.unit_price_minor
    shipment = await get_shipment(db, b.id)
    shipping = int(cfg["shipping_fee"].get(cur, 0)) if shipment else 0
    taxable = subtotal + addons
    tax_lines = []
    for rule in cfg.get("tax_rules") or []:
        amt = taxable * int(rule.get("rate_bps", 0)) // 10000
        tax_lines.append({"label": rule.get("label", "Tax"), "amount_minor": amt})
    tax = sum(t["amount_minor"] for t in tax_lines)
    b.subtotal_minor, b.addons_minor, b.shipping_minor, b.tax_minor = subtotal, addons, shipping, tax
    b.total_minor = subtotal + addons + shipping + b.dakshina_minor + tax
    return {
        "currency": cur, "package_minor": subtotal, "addons_minor": addons, "shipping_minor": shipping,
        "dakshina_minor": b.dakshina_minor, "tax_minor": tax, "tax_lines": tax_lines, "total_minor": b.total_minor,
        "occurrences": occurrences, "grand_total_minor": b.total_minor * occurrences,
    }


async def get_shipment(db: AsyncSession, booking_id: uuid.UUID) -> Shipment | None:
    return (await db.execute(select(Shipment).where(Shipment.booking_id == booking_id))).scalar_one_or_none()


# ------------------------------------------------------------------ payment
async def start_payment(db: AsyncSession, b: Booking, user: User, *, payment_mode: str = "full") -> dict:
    """Creates the gateway order (or mandate for AutoPay) and moves the booking to pending_payment."""
    if b.status not in (S.draft, S.pending_payment):
        raise BookingError("not_payable")
    ev = b.event
    if ev.booking_cutoff_at <= utcnow():
        raise BookingError("event_closed")
    if not b.names or not b.whatsapp_e164 or not b.consent_whatsapp_at:
        raise BookingError("incomplete")
    b.user_id = user.id
    puja = ev.puja
    provider = get_payment_provider()
    customer = Customer(name=b.names[0].name, phone_e164=b.whatsapp_e164, email=user.email)
    seva_plan = await _seva_plan(db, puja.id)

    reuse = await _open_payment(db, b)
    if reuse is not None:  # Pay pressed again within the window: reopen the same gateway order
        checkout = reuse.raw["checkout"]
    elif seva_plan is None or b.subscription_id:  # one-time puja, or "pay now" for one AutoPay occurrence
        await reprice(db, b)
        order = await provider.create_order(str(b.id), b.total_minor, b.currency, customer,
                                            {"booking_id": str(b.id), "booking_code": b.code})
        db.add(Payment(booking_id=b.id, subscription_id=b.subscription_id, provider=provider.name,
                       provider_order_id=order.order_id, amount_minor=b.total_minor, currency=b.currency,
                       status="created", raw={"checkout": order.checkout}))
        checkout = order.checkout
    else:
        checkout = await _start_seva_payment(db, b, user, seva_plan, payment_mode, provider, customer)

    b.payment_expires_at = utcnow() + PAYMENT_TTL
    if b.status == S.draft:
        await transition(db, b, S.pending_payment)
    return {"provider": provider.name, "checkout": checkout, "amount_minor": checkout.get("amount", b.total_minor),
            "currency": b.currency}


async def _open_payment(db: AsyncSession, b: Booking) -> Payment | None:
    if b.status != S.pending_payment or not b.payment_expires_at or b.payment_expires_at <= utcnow():
        return None
    cond = (Payment.booking_id == b.id) if not b.subscription_id else (
        (Payment.booking_id == b.id) | ((Payment.subscription_id == b.subscription_id) & Payment.booking_id.is_(None)))
    p = (await db.execute(select(Payment).where(cond, Payment.status == "created")
                          .order_by(Payment.created_at.desc()))).scalars().first()
    return p if p is not None and p.raw and "checkout" in p.raw else None


async def _seva_plan(db: AsyncSession, puja_id: int):
    from models import SevaPlan

    return (await db.execute(select(SevaPlan).where(SevaPlan.puja_id == puja_id))).scalar_one_or_none()


async def _start_seva_payment(db, b: Booking, user: User, plan, payment_mode, provider, customer) -> dict:
    from services.catalog import upcoming_events

    if b.currency != "INR" and payment_mode == "autopay":
        raise BookingError("autopay_inr_only")
    if payment_mode == "autopay" and not plan.autopay_allowed:
        raise BookingError("autopay_not_allowed")
    events = [e for e in await upcoming_events(db, plan.puja_id) if e.starts_at >= b.event.starts_at][: plan.occurrences]
    if len(events) < plan.occurrences:
        raise BookingError("seva_dates_unavailable")
    # Sevas carry no add-ons or prasad in v1; price is per occurrence.
    await reprice(db, b)
    per = b.total_minor

    sub = Subscription(user_id=user.id, seva_plan_id=plan.id, package_id=b.package_id,
                       payment_mode=PaymentMode(payment_mode), status=SubscriptionStatus.active,
                       next_occurrence_at=events[0].starts_at)
    db.add(sub)
    await db.flush()
    b.subscription_id = sub.id
    b.puja_event_id = events[0].id
    for ev in events[1:]:
        clone = Booking(
            code=await new_booking_code(db), user_id=user.id, puja_event_id=ev.id, package_id=b.package_id,
            subscription_id=sub.id, locale=b.locale, currency=b.currency, subtotal_minor=b.subtotal_minor,
            dakshina_minor=b.dakshina_minor, tax_minor=b.tax_minor, total_minor=per,
            status=S.pending_payment if payment_mode == "full" else S.draft, whatsapp_e164=b.whatsapp_e164,
            wish=b.wish, consent_whatsapp_at=b.consent_whatsapp_at, consent_text_version=b.consent_text_version,
            proof_token=proof_token(),
        )
        from models import BookingName

        clone.names = [BookingName(position=n.position, name=n.name, relation=n.relation, gotra=n.gotra,
                                   gotra_unknown=n.gotra_unknown, nakshatra=n.nakshatra) for n in b.names]
        if payment_mode == "full":
            clone.payment_expires_at = utcnow() + PAYMENT_TTL
        db.add(clone)

    if payment_mode == "full":
        total = per * plan.occurrences
        order = await provider.create_order(str(sub.id), total, b.currency, customer,
                                            {"subscription_id": str(sub.id), "booking_code": b.code})
        checkout = {**order.checkout, "amount": total}
        db.add(Payment(subscription_id=sub.id, provider=provider.name, provider_order_id=order.order_id,
                       amount_minor=total, currency=b.currency, status="created", raw={"checkout": checkout}))
        return checkout

    cap = await site_config.get(db, "autopay_max_inr_minor")
    if per > cap:
        raise BookingError("autopay_above_cap")
    last = events[-1].starts_at
    mandate_ref = await provider.create_mandate(str(sub.id), per, "weekly", utcnow(), last + timedelta(days=7),
                                                customer)
    mandate = Mandate(subscription_id=sub.id, provider=provider.name, token=mandate_ref.token,
                      max_amount_minor=per, frequency="weekly", status=mandate_ref.status)
    db.add(mandate)
    await db.flush()
    sub.mandate_id = mandate.id
    first = mandate_ref.first_order
    if first is None:  # fake gateway: first debit is a normal order tied to the mandate
        first = await provider.create_order(str(b.id), per, "INR", customer,
                                            {"booking_id": str(b.id), "mandate_id": mandate_ref.mandate_id})
    checkout = {**first.checkout, "amount": per, "autopay": True}
    db.add(Payment(booking_id=b.id, subscription_id=sub.id, provider=provider.name,
                   provider_order_id=first.order_id, amount_minor=per, currency="INR", status="created",
                   raw={"mandate_ref": mandate_ref.mandate_id, "checkout": checkout}))
    return checkout


async def on_payment_event(db: AsyncSession, ev: PaymentEvent, provider_name: str) -> None:
    if ev.kind == "payment_captured":
        await _on_captured(db, ev, provider_name)
    elif ev.kind == "payment_failed":
        await _on_failed(db, ev)
    elif ev.kind in ("refund_processed", "refund_failed"):
        await _on_refund(db, ev)
    elif ev.kind in ("mandate_active", "mandate_failed", "mandate_cancelled"):
        from services import seva

        await seva.on_mandate_event(db, ev)


async def _find_payment(db: AsyncSession, ev: PaymentEvent) -> Payment | None:
    if ev.order_id:
        p = (await db.execute(select(Payment).where(Payment.provider_order_id == ev.order_id)
                              .with_for_update())).scalar_one_or_none()
        if p:
            return p
    if ev.payment_id:
        return (await db.execute(select(Payment).where(Payment.provider_payment_id == ev.payment_id)
                                 .with_for_update())).scalar_one_or_none()
    return None


async def _on_captured(db: AsyncSession, ev: PaymentEvent, provider_name: str) -> None:
    pay = await _find_payment(db, ev)
    if pay is None:
        log(logger, "captured payment with unknown order", order_id=ev.order_id, payment_id=ev.payment_id)
        return
    if pay.status == "captured":
        return  # replayed webhook
    if ev.amount_minor is not None and ev.amount_minor != pay.amount_minor:
        pay.status = "amount_mismatch"
        pay.raw = ev.raw
        from services.alerts import ops_alert

        await ops_alert("Payment amount mismatch", f"order {pay.provider_order_id}: expected {pay.amount_minor}, "
                        f"got {ev.amount_minor}", payment_id=str(pay.id))
        return
    pay.status, pay.provider_payment_id, pay.raw = "captured", ev.payment_id, ev.raw

    if pay.subscription_id and ev.mandate_token:
        from services import seva

        await seva.activate_mandate(db, pay.subscription_id, ev.mandate_token)

    if pay.booking_id:
        targets = [await db.get(Booking, pay.booking_id)]
    else:
        targets = list((await db.execute(
            select(Booking).where(Booking.subscription_id == pay.subscription_id).order_by(Booking.created_at)
        )).scalars())
    for b in targets:
        if b is None:
            continue
        if b.status in (S.pending_payment, S.draft):
            if b.status == S.draft:
                b.status = S.pending_payment
            await confirm(db, b)
        elif b.status == S.cancelled and b.cancel_reason == "payment_expired":
            # Paid after the draft was released: refund instead of silently keeping the money.
            await refund_booking(db, b, b.total_minor, "late_payment_after_expiry", payment=pay)


async def _on_failed(db: AsyncSession, ev: PaymentEvent) -> None:
    pay = await _find_payment(db, ev)
    if pay is None or pay.status == "captured":
        return
    pay.status = "failed"
    pay.raw = ev.raw
    if pay.booking_id:
        b = await db.get(Booking, pay.booking_id)
        if b and b.subscription_id:
            from services import seva

            await seva.on_debit_failed(db, b)


async def confirm(db: AsyncSession, b: Booking) -> None:
    await transition(db, b, S.confirmed)
    user = await db.get(User, b.user_id) if b.user_id else None
    if user and not user.whatsapp_opt_in_at:
        user.whatsapp_opt_in_at = b.consent_whatsapp_at or utcnow()
    c = await ctx(db, b)
    await notify.queue(db, template_key="booking_confirmed", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       params=[c["name"], c["puja"], c["temple"], c["datetime_ist"], c["package"], b.code],
                       button_params=[booking_path(b)])
    await schedule_reminder(db, b, c)
    ev = c["event"]
    if ev.locked_at:  # paid in the last moments before cutoff; join the printed sheet at the end
        from services import events as event_svc

        await transition(db, b, S.locked)
        await event_svc.append_to_sheet(db, ev, b)


async def schedule_reminder(db: AsyncSession, b: Booking, c: dict | None = None) -> None:
    c = c or await ctx(db, b)
    ev = c["event"]
    user = c["user"]
    at = reminder_time(ev.starts_at, tz_for_phone(b.whatsapp_e164, user.timezone if user else None))
    if at <= utcnow():
        return
    await notify.queue(db, template_key="puja_reminder", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       occurrence_key=f"event:{ev.id}", scheduled_for=at,
                       params=[c["name"], c["puja"], c["temple"], c["datetime_ist"]])


# ------------------------------------------------------------------ cancellation + refunds
def can_devotee_cancel(b: Booking) -> bool:
    return b.status == S.confirmed and b.event.booking_cutoff_at > utcnow()


async def cancel(db: AsyncSession, b: Booking, *, reason: str, staff_id: int | None = None,
                 refund_minor: int | None = None) -> None:
    """Cancels + refunds (full by default). Used for devotee cancel, ops cancel, event cancellation."""
    if b.status == S.cancelled:
        return
    paid = b.status not in (S.draft, S.pending_payment)
    await transition(db, b, S.cancelled, staff_id=staff_id, reason=reason)
    await notify.cancel_queued(db, b.id, ["puja_reminder"])
    amount = (b.total_minor if refund_minor is None else refund_minor) if paid else 0
    c = await ctx(db, b)
    if paid:
        await notify.queue(db, template_key="booking_cancelled", to=b.whatsapp_e164, locale=b.locale, booking=b,
                           params=[c["puja"], b.code, fmt_money(amount, b.currency, b.locale)])
    if amount > 0:
        await refund_booking(db, b, amount, reason)
    if b.subscription_id:
        from services import seva

        await seva.after_occurrence_cancelled(db, b)


async def payment_for(db: AsyncSession, b: Booking) -> Payment | None:
    p = (await db.execute(select(Payment).where(Payment.booking_id == b.id, Payment.status == "captured")
                          .order_by(Payment.created_at.desc()))).scalars().first()
    if p is None and b.subscription_id:
        p = (await db.execute(select(Payment).where(Payment.subscription_id == b.subscription_id,
                                                    Payment.booking_id.is_(None), Payment.status == "captured")
                              )).scalars().first()
    return p


async def refund_booking(db: AsyncSession, b: Booking, amount_minor: int, reason: str,
                         payment: Payment | None = None) -> Refund | None:
    pay = payment or await payment_for(db, b)
    if pay is None:
        log(logger, "refund requested without captured payment", booking_id=str(b.id))
        return None
    already = sum(r.amount_minor for r in (await db.execute(
        select(Refund).where(Refund.payment_id == pay.id, Refund.status != "failed"))).scalars())
    amount_minor = min(amount_minor, pay.amount_minor - already)
    if amount_minor <= 0:
        return None
    idem = f"refund:{b.id}:{reason}"[:60]
    existing = (await db.execute(select(Refund).where(Refund.booking_id == b.id, Refund.reason == reason))
                ).scalar_one_or_none()
    if existing:
        return existing
    refund = Refund(payment_id=pay.id, booking_id=b.id, amount_minor=amount_minor, reason=reason, status="requested")
    db.add(refund)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise
    provider = get_payment_provider(pay.provider)
    ref = await provider.refund(pay.provider_payment_id or pay.provider_order_id or "", amount_minor, reason, idem)
    refund.provider_refund_id = ref.refund_id
    log(logger, "refund requested", booking_id=str(b.id), amount_minor=amount_minor, refund_id=ref.refund_id)
    if provider.name == "fake":
        from services.jobs import enqueue

        await enqueue("fake_payment_webhook", {"kind": "refund_processed", "refund_id": ref.refund_id,
                                               "payment_id": pay.provider_payment_id, "amount_minor": amount_minor},
                      _defer_by=2)
    return refund


async def _on_refund(db: AsyncSession, ev: PaymentEvent) -> None:
    refund = (await db.execute(select(Refund).where(Refund.provider_refund_id == ev.refund_id).with_for_update()
                               )).scalar_one_or_none()
    if refund is None or refund.status == "processed":
        return
    if ev.kind == "refund_failed":
        refund.status = "failed"
        from services.alerts import ops_alert

        await ops_alert("Refund failed", f"refund {ev.refund_id}", booking_id=str(refund.booking_id))
        return
    refund.status = "processed"
    b = await db.get(Booking, refund.booking_id) if refund.booking_id else None
    if b is None:
        return
    if b.status == S.cancelled:
        await transition(db, b, S.refunded)
    days = await site_config.get(db, "refund_expected_days")
    await notify.queue(db, template_key="refund_processed", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       occurrence_key=f"refund:{refund.id}",
                       params=[fmt_money(refund.amount_minor, b.currency, b.locale), refund.provider_refund_id or "",
                               days])


# ------------------------------------------------------------------ fulfilment hooks
async def on_proof_sent(db: AsyncSession, b: Booking) -> None:
    if b.status != S.proof_ready:
        return
    await transition(db, b, S.proof_sent)
    c = await ctx(db, b)
    await notify.queue(db, template_key="feedback_request", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       params=[c["name"], c["puja"]], scheduled_for=utcnow() + timedelta(days=2))
    await maybe_complete(db, b)


async def maybe_complete(db: AsyncSession, b: Booking) -> None:
    if b.status != S.proof_sent:
        return
    sh = await get_shipment(db, b.id)
    if sh is None or sh.status == ShipmentStatus.delivered:
        await transition(db, b, S.completed)


async def answer_reschedule(db: AsyncSession, b: Booking, *, accept: bool, staff_id: int | None = None) -> None:
    if b.status != S.rescheduled:
        return
    if not accept:
        await cancel(db, b, reason="reschedule_refund", staff_id=staff_id)
        return
    ev = await db.get(PujaEvent, b.puja_event_id)  # already points to the new event
    await transition(db, b, S.locked if ev.locked_at else S.confirmed, staff_id=staff_id)
    b.reschedule_deadline_at = None
    await schedule_reminder(db, b)
    if ev.locked_at:
        from services import events as event_svc

        await event_svc.append_to_sheet(db, ev, b)


async def expire_unpaid(db: AsyncSession) -> int:
    """Releases unpaid orders after 30 minutes. AutoPay occurrences get `payment_expires_at = cutoff`,
    so an occurrence still unpaid at cutoff is skipped (no puja, no charge) and the next one proceeds."""
    rows = (await db.execute(
        select(Booking).where(Booking.status == S.pending_payment, Booking.payment_expires_at < utcnow())
    )).scalars().all()
    for b in rows:
        sub = await db.get(Subscription, b.subscription_id) if b.subscription_id else None
        autopay = sub is not None and sub.payment_mode == PaymentMode.autopay and b.confirmed_at is None
        await transition(db, b, S.cancelled, reason="autopay_unpaid" if autopay and b.cancel_reason is None
                         and await _is_later_occurrence(db, b) else "payment_expired")
        if sub and sub.status == SubscriptionStatus.active and not await _has_live_occurrences(db, sub.id):
            sub.status = SubscriptionStatus.cancelled
    return len(rows)


async def _is_later_occurrence(db: AsyncSession, b: Booking) -> bool:
    first = (await db.execute(select(Booking.id).where(Booking.subscription_id == b.subscription_id)
                              .order_by(Booking.created_at).limit(1))).scalar_one()
    return first != b.id


async def _has_live_occurrences(db: AsyncSession, sub_id) -> bool:
    live = (await db.execute(select(Booking.id).where(
        Booking.subscription_id == sub_id,
        Booking.status.not_in([S.cancelled, S.refunded])).limit(1))).first()
    return live is not None


def is_dev_fake() -> bool:
    return settings.payment_provider == "fake"
