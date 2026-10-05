"""Recurring sevas — PRD §8: full payment or UPI AutoPay.

Debit schedule per occurrence (T = puja time): pre-debit notice at T-50h, debit at T-25h, cutoff at T-12h.
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logging_setup import log
from models import (
    Booking,
    BookingStatus,
    Mandate,
    Payment,
    PaymentMode,
    PujaEvent,
    Subscription,
    SubscriptionStatus,
)
from providers.payments import get_payment_provider
from providers.payments.base import PaymentEvent
from services import notify
from services.i18n import fmt_date, fmt_money, utcnow

logger = logging.getLogger("seva")
S = BookingStatus
PREDEBIT_BEFORE = timedelta(hours=50)
DEBIT_BEFORE = timedelta(hours=25)
FAIL_SUFFIX = "0000003"  # fake gateway: numbers ending in this decline mandate debits


async def activate_mandate(db: AsyncSession, sub_id: uuid.UUID, token: str) -> None:
    sub = await db.get(Subscription, sub_id)
    if sub is None or sub.mandate_id is None:
        return
    m = await db.get(Mandate, sub.mandate_id)
    if m and m.status != "cancelled":
        m.token, m.status = token, "active"


async def on_mandate_event(db: AsyncSession, ev: PaymentEvent) -> None:
    m = None
    if ev.mandate_token:
        m = (await db.execute(select(Mandate).where(Mandate.token == ev.mandate_token))).scalar_one_or_none()
    if m is None and ev.mandate_ref:
        m = (await db.execute(select(Mandate).where(Mandate.token.like(f"{ev.mandate_ref}%")))).scalars().first()
    if m is None:
        return
    sub = await db.get(Subscription, m.subscription_id)
    if ev.kind == "mandate_active":
        m.status = "active"
        if ev.mandate_token:
            m.token = ev.mandate_token
    elif ev.kind == "mandate_cancelled":
        m.status = "cancelled"
        if sub and sub.status == SubscriptionStatus.active:
            await cancel_subscription(db, sub, by_gateway=True)
    else:
        m.status = "failed"
        if sub and sub.status == SubscriptionStatus.active:
            sub.status = SubscriptionStatus.mandate_failed


async def _occurrences(db: AsyncSession, sub_id: uuid.UUID) -> list[Booking]:
    return list((await db.execute(
        select(Booking).join(PujaEvent, Booking.puja_event_id == PujaEvent.id)
        .where(Booking.subscription_id == sub_id).order_by(PujaEvent.starts_at)
    )).scalars())


async def autopay_tick(db: AsyncSession) -> dict:
    """Runs every few minutes: sends pre-debit notices and triggers debits that are due."""
    now = utcnow()
    stats = {"predebit": 0, "debited": 0}
    subs = (await db.execute(select(Subscription).where(
        Subscription.status == SubscriptionStatus.active, Subscription.payment_mode == PaymentMode.autopay
    ))).scalars().all()
    provider = get_payment_provider()
    for sub in subs:
        mandate = await db.get(Mandate, sub.mandate_id) if sub.mandate_id else None
        if mandate is None or mandate.status != "active" or not mandate.token:
            continue
        for b in await _occurrences(db, sub.id):
            ev = b.event
            if b.status != S.draft or ev.starts_at <= now:
                continue
            seva_title = (await _title(db, b))
            if now >= ev.starts_at - PREDEBIT_BEFORE:
                qid = await notify.queue(
                    db, template_key="seva_predebit", to=b.whatsapp_e164, locale=b.locale, booking=b,
                    occurrence_key=f"predebit:{ev.id}",
                    params=[seva_title, fmt_money(b.total_minor, b.currency, b.locale),
                            fmt_date(ev.starts_at - DEBIT_BEFORE, b.locale), mandate.token.split(":")[-1][:20]],
                    button_params=[f"{b.locale}/account/subscriptions"])
                stats["predebit"] += 1 if qid else 0
            if now >= ev.starts_at - DEBIT_BEFORE and ev.booking_cutoff_at > now:
                idem = f"debit:{b.id}"
                charge = await provider.charge_mandate(mandate.token, b.total_minor, idem)
                db.add(Payment(booking_id=b.id, subscription_id=sub.id, provider=provider.name,
                               provider_order_id=charge.order_id, provider_payment_id=charge.payment_id,
                               amount_minor=b.total_minor, currency=b.currency, status="created"))
                b.status = S.pending_payment
                b.payment_expires_at = ev.booking_cutoff_at  # unpaid at cutoff -> skipped
                stats["debited"] += 1
                log(logger, "autopay debit", booking_id=str(b.id), amount_minor=b.total_minor)
                if provider.name == "fake":
                    from services.jobs import enqueue

                    failed = (b.whatsapp_e164 or "").endswith(FAIL_SUFFIX)
                    await enqueue("fake_payment_webhook", {
                        "kind": "payment_failed" if failed else "payment_captured", "order_id": charge.order_id,
                        "payment_id": f"fake_pay_{uuid.uuid4().hex[:12]}", "amount_minor": b.total_minor,
                        "currency": b.currency}, _defer_by=2)
        upcoming = [b for b in await _occurrences(db, sub.id) if b.event.starts_at > now
                    and b.status not in (S.cancelled, S.refunded)]
        sub.next_occurrence_at = upcoming[0].event.starts_at if upcoming else None
    return stats


async def _title(db: AsyncSession, b: Booking) -> str:
    from services.catalog import puja_title

    return await puja_title(db, b.event.puja_id, b.locale)


async def on_debit_failed(db: AsyncSession, b: Booking) -> None:
    sub = await db.get(Subscription, b.subscription_id)
    if sub is None or sub.payment_mode != PaymentMode.autopay:
        return
    await notify.queue(db, template_key="seva_payment_failed", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       occurrence_key=f"debit_failed:{b.puja_event_id}",
                       params=[await _title(db, b), fmt_date(b.event.starts_at, b.locale),
                               fmt_money(b.total_minor, b.currency, b.locale)],
                       button_params=[f"{b.locale}/checkout/{b.id}"])


async def cancel_subscription(db: AsyncSession, sub: Subscription, *, by_gateway: bool = False,
                              staff_id: int | None = None) -> dict:
    """One tap: cancels the mandate and every future occurrence. Full-payment occurrences whose cutoff
    has not passed are refunded (PRD §8)."""
    from services import bookings as booking_svc

    if sub.status not in (SubscriptionStatus.active, SubscriptionStatus.mandate_failed):
        return {"cancelled": 0}
    sub.status = SubscriptionStatus.cancelled
    sub.cancelled_at = utcnow()
    if sub.mandate_id and not by_gateway:
        m = await db.get(Mandate, sub.mandate_id)
        if m and m.token and m.status != "cancelled":
            await get_payment_provider(m.provider).cancel_mandate(m.token)
        if m:
            m.status = "cancelled"
    n = 0
    now = utcnow()
    for b in await _occurrences(db, sub.id):
        if b.event.booking_cutoff_at <= now:
            continue
        if b.status in (S.draft, S.pending_payment):
            await booking_svc.transition(db, b, S.cancelled, reason="subscription_cancelled", staff_id=staff_id)
            n += 1
        elif b.status == S.confirmed:
            await booking_svc.cancel(db, b, reason="subscription_cancelled", staff_id=staff_id)
            n += 1
    sub.next_occurrence_at = None
    return {"cancelled": n}


async def after_occurrence_cancelled(db: AsyncSession, b: Booking) -> None:
    sub = await db.get(Subscription, b.subscription_id)
    if sub is None or sub.status != SubscriptionStatus.active:
        return
    live = [o for o in await _occurrences(db, sub.id) if o.status not in (S.cancelled, S.refunded)]
    if not live:
        sub.status = SubscriptionStatus.cancelled


async def subscriptions_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    from services.catalog import puja_title

    out = []
    subs = (await db.execute(select(Subscription).where(Subscription.user_id == user_id)
                             .order_by(Subscription.created_at.desc()))).scalars().all()
    for sub in subs:
        occ = await _occurrences(db, sub.id)
        if not occ:
            continue
        mandate = await db.get(Mandate, sub.mandate_id) if sub.mandate_id else None
        first = occ[0]
        out.append({
            "id": str(sub.id), "status": sub.status.value, "payment_mode": sub.payment_mode.value,
            "mandate_status": mandate.status if mandate else None,
            "next_occurrence_at": sub.next_occurrence_at.isoformat() if sub.next_occurrence_at else None,
            "title": await puja_title(db, first.event.puja_id, first.locale), "puja_id": first.event.puja_id,
            "per_occurrence_minor": first.total_minor, "currency": first.currency,
            "occurrences": [{"booking_id": str(o.id), "code": o.code, "status": o.status.value,
                             "starts_at": o.event.starts_at.isoformat()} for o in occ],
        })
    return out
