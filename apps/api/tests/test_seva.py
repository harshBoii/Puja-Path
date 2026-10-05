"""M5 acceptance: 3-occurrence AutoPay seva debits on schedule with a pre-debit message before each; one-tap cancel."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from db import SessionLocal
from models import (
    Booking,
    BookingStatus,
    FakeProviderCall,
    Mandate,
    MessageLog,
    Payment,
    PujaEvent,
    Subscription,
    SubscriptionStatus,
)
from routers.dev import deliver
from services import seva
from tests.conftest import book, login

S = BookingStatus
DEEPA = 9  # Nitya Deepa Seva: daily, 3 occurrences


async def _subscribe(client, mode: str) -> tuple[uuid.UUID, dict]:
    res = await book(client, puja_id=DEEPA, pay=False)
    await login(client, "+919876543210")
    per = res["view"]["pricing"]["total_minor"]
    expected = per * 3 if mode == "full" else per
    r = await client.post(f"/v1/drafts/{res['draft_id']}/pay", json={
        "consent_terms": True, "payment_mode": mode, "expected_total_minor": expected})
    assert r.status_code == 200, r.text
    assert r.json()["amount_minor"] == expected
    r2 = await client.post(f"/v1/dev/fake-gateway/{r.json()['checkout']['order_id']}", json={"outcome": "success"})
    assert r2.status_code == 200
    async with SessionLocal() as db:
        b = await db.get(Booking, uuid.UUID(res["draft_id"]))
        return b.subscription_id, res


async def _occurrences(sub_id):
    async with SessionLocal() as db:
        return list((await db.execute(select(Booking).join(PujaEvent, Booking.puja_event_id == PujaEvent.id)
                                      .where(Booking.subscription_id == sub_id)
                                      .order_by(PujaEvent.starts_at))).scalars())


async def test_autopay_three_occurrences_debit_on_schedule(client, monkeypatch):
    sub_id, _ = await _subscribe(client, "autopay")
    occ = await _occurrences(sub_id)
    assert [o.status for o in occ] == [S.confirmed, S.draft, S.draft]
    async with SessionLocal() as db:
        sub = await db.get(Subscription, sub_id)
        mandate = await db.get(Mandate, sub.mandate_id)
    assert mandate.status == "active" and mandate.token  # first debit registered the mandate

    for o in occ[1:]:
        t = o.event.starts_at
        # T-50h: pre-debit notice, no debit yet
        monkeypatch.setattr(seva, "utcnow", lambda t=t: t - timedelta(hours=50) + timedelta(minutes=1))
        async with SessionLocal() as db:
            stats = await seva.autopay_tick(db)
            await db.commit()
        async with SessionLocal() as db:
            pre = (await db.execute(select(MessageLog).where(MessageLog.booking_id == o.id,
                                                             MessageLog.template_key == "seva_predebit"))).scalar_one()
            assert (await db.execute(select(Payment).where(Payment.booking_id == o.id))).first() is None
        # T-25h: debit through the mandate; gateway confirms by webhook
        monkeypatch.setattr(seva, "utcnow", lambda t=t: t - timedelta(hours=25) + timedelta(minutes=1))
        async with SessionLocal() as db:
            stats = await seva.autopay_tick(db)
            await db.commit()
        assert stats["debited"] == 1
        async with SessionLocal() as db:
            pay = (await db.execute(select(Payment).where(Payment.booking_id == o.id))).scalar_one()
        assert pre.created_at <= pay.created_at
        await deliver({"kind": "payment_captured", "order_id": pay.provider_order_id, "payment_id": f"p-{o.code}",
                       "amount_minor": pay.amount_minor, "currency": "INR"})
    occ = await _occurrences(sub_id)
    assert [o.status for o in occ] == [S.confirmed, S.confirmed, S.confirmed]
    async with SessionLocal() as db:
        charges = (await db.execute(select(FakeProviderCall).where(FakeProviderCall.method == "charge_mandate"))
                   ).scalars().all()
    assert len(charges) == 2


async def test_failed_debit_sends_pay_now_and_skips_at_cutoff(client, monkeypatch):
    from services import bookings as booking_svc

    sub_id, _ = await _subscribe(client, "autopay")
    o = (await _occurrences(sub_id))[1]
    t = o.event.starts_at
    monkeypatch.setattr(seva, "utcnow", lambda: t - timedelta(hours=25) + timedelta(minutes=1))
    async with SessionLocal() as db:
        await seva.autopay_tick(db)
        await db.commit()
        pay = (await db.execute(select(Payment).where(Payment.booking_id == o.id))).scalar_one()
    await deliver({"kind": "payment_failed", "order_id": pay.provider_order_id})
    async with SessionLocal() as db:
        failed = (await db.execute(select(MessageLog).where(MessageLog.booking_id == o.id,
                                                            MessageLog.template_key == "seva_payment_failed"))
                  ).scalar_one()
        assert failed.button_params == [f"en/checkout/{o.id}"]
        # still unpaid at cutoff -> that occurrence is skipped, the next one proceeds
        b = await db.get(Booking, o.id)
        b.payment_expires_at = b.event.booking_cutoff_at = t - timedelta(days=30)
        await db.commit()
        await booking_svc.expire_unpaid(db)
        await db.commit()
        b = await db.get(Booking, o.id)
        sub = await db.get(Subscription, sub_id)
    assert b.status == S.cancelled and b.cancel_reason == "autopay_unpaid"
    assert sub.status == SubscriptionStatus.active


async def test_cancel_subscription_stops_all_future_debits(client, monkeypatch):
    sub_id, _ = await _subscribe(client, "autopay")
    r = await client.post(f"/v1/account/subscriptions/{sub_id}/cancel")  # one call, like the one Pay that started it
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    occ = await _occurrences(sub_id)
    assert [o.status for o in occ[1:]] == [S.cancelled, S.cancelled]
    for o in occ[1:]:
        t = o.event.starts_at
        monkeypatch.setattr(seva, "utcnow", lambda t=t: t - timedelta(hours=25) + timedelta(minutes=1))
        async with SessionLocal() as db:
            assert (await seva.autopay_tick(db))["debited"] == 0
    async with SessionLocal() as db:
        calls = [c.method for c in (await db.execute(select(FakeProviderCall).where(
            FakeProviderCall.kind == "payments"))).scalars()]
    assert "cancel_mandate" in calls and "charge_mandate" not in calls


async def test_full_payment_covers_every_occurrence(client):
    sub_id, res = await _subscribe(client, "full")
    occ = await _occurrences(sub_id)
    assert [o.status for o in occ] == [S.confirmed] * 3
    async with SessionLocal() as db:
        pays = (await db.execute(select(Payment).where(Payment.subscription_id == sub_id))).scalars().all()
    assert len(pays) == 1 and pays[0].amount_minor == res["view"]["pricing"]["total_minor"] * 3


async def test_full_payment_cancel_refunds_remaining_occurrences(client):
    sub_id, res = await _subscribe(client, "full")
    r = await client.post(f"/v1/account/subscriptions/{sub_id}/cancel")
    assert r.json()["cancelled"] == 3
    async with SessionLocal() as db:
        from models import Refund

        refunds = (await db.execute(select(Refund))).scalars().all()
    assert len(refunds) == 3 and all(x.amount_minor == res["view"]["pricing"]["total_minor"] for x in refunds)


async def test_my_subscriptions_lists_dates_and_mandate(client):
    sub_id, _ = await _subscribe(client, "autopay")
    subs = (await client.get("/v1/account/subscriptions")).json()
    assert subs[0]["payment_mode"] == "autopay" and subs[0]["mandate_status"] == "active"
    assert len(subs[0]["occurrences"]) == 3
