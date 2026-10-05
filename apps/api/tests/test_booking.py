"""M2 acceptance: end-to-end booking, webhook idempotency, cancellation and refunds."""

import asyncio
from datetime import timedelta

from sqlalchemy import func, select, update

from db import SessionLocal
from models import Booking, BookingStatus, MessageLog, Payment, PujaEvent, Refund
from routers.dev import deliver
from services import site_config
from tests.conftest import book, login


async def _booking(draft_id) -> Booking:
    async with SessionLocal() as db:
        return await db.get(Booking, __import__("uuid").UUID(draft_id))


async def test_detail_to_confirmed_end_to_end(client):
    res = await book(client)
    b = await _booking(res["draft_id"])
    assert b.status == BookingStatus.confirmed
    assert b.confirmed_at is not None
    async with SessionLocal() as db:
        msgs = (await db.execute(select(MessageLog).where(MessageLog.booking_id == b.id))).scalars().all()
    keys = {m.template_key for m in msgs}
    assert "booking_confirmed" in keys
    assert "puja_reminder" in keys  # scheduled for 18:00 local the day before
    status = (await client.get(f"/v1/bookings/{b.id}/status")).json()
    assert status["status"] == "confirmed"


async def test_server_prices_and_rejects_changed_total(client):
    res = await book(client, pay=False)
    await login(client, "+919876543210")
    r = await client.post(f"/v1/drafts/{res['draft_id']}/pay", json={"consent_terms": True, "expected_total_minor": 1})
    assert r.status_code == 409 and r.json()["detail"] == "price_changed"


async def test_no_preticked_paid_addons(client):
    detail = (await client.get("/v1/en/pujas/2")).json()
    r = await client.post("/v1/drafts", json={"puja_id": 2, "package_id": detail["packages"][0]["id"]})
    view = (await client.get(f"/v1/drafts/{r.json()['id']}")).json()
    assert view["addons"] == [] and view["dakshina_minor"] == 0 and view["prasad"] is False
    assert view["consent_marketing"] is False
    assert view["pricing"]["total_minor"] == detail["packages"][0]["price_minor"]


async def test_payment_webhook_replayed_five_times_confirms_once(client):
    res = await book(client, pay=False)
    await login(client, "+919876543210")
    view = res["view"]
    r = await client.post(f"/v1/drafts/{res['draft_id']}/pay", json={
        "consent_terms": True, "expected_total_minor": view["pricing"]["total_minor"]})
    order_id = r.json()["checkout"]["order_id"]
    event = {"kind": "payment_captured", "event_id": "evt_replay_1", "order_id": order_id,
             "payment_id": "fake_pay_replay", "amount_minor": view["pricing"]["total_minor"], "currency": "INR"}
    # two concurrent, then three sequential replays of the very same signed event
    await asyncio.gather(deliver(dict(event)), deliver(dict(event)))
    for _ in range(3):
        await deliver(dict(event))
    # a gateway retry with a different event id for the same order is also a no-op
    await deliver({**event, "event_id": "evt_replay_2"})
    async with SessionLocal() as db:
        b = await db.get(Booking, __import__("uuid").UUID(res["draft_id"]))
        confirmations = (await db.execute(select(func.count()).select_from(MessageLog).where(
            MessageLog.booking_id == b.id, MessageLog.template_key == "booking_confirmed"))).scalar()
        captured = (await db.execute(select(func.count()).select_from(Payment).where(
            Payment.booking_id == b.id, Payment.status == "captured"))).scalar()
    assert b.status == BookingStatus.confirmed
    assert confirmations == 1
    assert captured == 1


async def test_bad_signature_rejected(client):
    r = await client.post("/v1/webhooks/payments/fake", content=b'{"kind":"payment_captured"}',
                          headers={"x-fake-signature": "nope"})
    assert r.status_code == 401


async def test_cancel_before_cutoff_full_refund(client):
    res = await book(client)
    bid = res["draft_id"]
    detail = (await client.get(f"/v1/account/bookings/{bid}")).json()
    assert detail["can_cancel"] is True
    r = await client.post(f"/v1/account/bookings/{bid}/cancel")
    assert r.status_code == 200
    async with SessionLocal() as db:
        refund = (await db.execute(select(Refund).where(Refund.booking_id == __import__("uuid").UUID(bid)))).scalar_one()
    assert refund.amount_minor == res["view"]["pricing"]["total_minor"]
    # gateway confirms the refund
    await deliver({"kind": "refund_processed", "refund_id": refund.provider_refund_id,
                   "amount_minor": refund.amount_minor})
    b = await _booking(bid)
    assert b.status == BookingStatus.refunded
    async with SessionLocal() as db:
        keys = {m.template_key for m in (await db.execute(
            select(MessageLog).where(MessageLog.booking_id == b.id))).scalars()}
        reminder = (await db.execute(select(MessageLog).where(
            MessageLog.booking_id == b.id, MessageLog.template_key == "puja_reminder"))).scalar_one()
    assert {"booking_cancelled", "refund_processed"} <= keys
    assert reminder.status.value == "failed" and reminder.error_code == "superseded"


async def test_cancel_option_gone_after_cutoff(client):
    res = await book(client)
    bid = res["draft_id"]
    async with SessionLocal() as db:
        b = await db.get(Booking, __import__("uuid").UUID(bid))
        await db.execute(update(PujaEvent).where(PujaEvent.id == b.puja_event_id).values(
            booking_cutoff_at=PujaEvent.starts_at - timedelta(days=30)))
        await db.commit()
    detail = (await client.get(f"/v1/account/bookings/{bid}")).json()
    assert detail["can_cancel"] is False
    r = await client.post(f"/v1/account/bookings/{bid}/cancel")
    assert r.status_code == 409


async def test_late_payment_after_expiry_is_refunded(client):
    from services import bookings as booking_svc

    res = await book(client, pay=False)
    await login(client, "+919876543210")
    r = await client.post(f"/v1/drafts/{res['draft_id']}/pay", json={
        "consent_terms": True, "expected_total_minor": res["view"]["pricing"]["total_minor"]})
    order_id = r.json()["checkout"]["order_id"]
    async with SessionLocal() as db:
        await db.execute(update(Booking).values(payment_expires_at=Booking.created_at - timedelta(minutes=1)))
        await booking_svc.expire_unpaid(db)
        await db.commit()
    await client.post(f"/v1/dev/fake-gateway/{order_id}", json={"outcome": "success"})
    b = await _booking(res["draft_id"])
    assert b.status == BookingStatus.cancelled and b.cancel_reason == "payment_expired"
    async with SessionLocal() as db:
        assert (await db.execute(select(func.count()).select_from(Refund))).scalar() == 1


async def test_prasad_adds_shipping_and_requires_serviceable_pincode(client):
    res = await book(client, puja_id=2, prasad=True, pay=False, nakshatra="Rohini")
    fee = (await client.get("/v1/config")).json()["shipping_fee"]["INR"]
    assert res["view"]["pricing"]["shipping_minor"] == fee
    r = await client.put(f"/v1/drafts/{res['draft_id']}", json={"prasad": True, "address": {
        "name": "A", "phone": "+919876543210", "line1": "Line 1", "city": "Pune", "state": "MH", "pincode": "999999"}})
    assert r.status_code == 400 and r.json()["detail"] == "pincode_not_serviceable"


async def test_nakshatra_required_when_puja_requires_it(client):
    detail = (await client.get("/v1/en/pujas/2")).json()
    assert detail["requires_nakshatra"] is True
    r = await client.post("/v1/drafts", json={"puja_id": 2, "package_id": detail["packages"][0]["id"]})
    r = await client.put(f"/v1/drafts/{r.json()['id']}", json={"names": [{"name": "Ravi", "gotra": "Atri"}]})
    assert r.status_code == 400 and r.json()["detail"] == "nakshatra_required"


async def test_gotra_unknown_uses_config_fallback(client):
    res = await book(client, names=[{"name": "Ravi", "gotra_unknown": True}], pay=False)
    async with SessionLocal() as db:
        fallback = await site_config.get(db, "gotra_fallback")
    assert res["view"]["gotra_fallback"] == fallback["en"]
    assert res["view"]["names"][0]["gotra_unknown"] is True


async def test_invoice_and_calendar(client):
    res = await book(client)
    r = await client.get(f"/v1/account/bookings/{res['draft_id']}/invoice.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    r = await client.get(f"/v1/account/bookings/{res['draft_id']}/calendar.ics")
    assert r.status_code == 200 and b"BEGIN:VEVENT" in r.content


async def test_otp_rate_limit(client):
    for _ in range(5):
        assert (await client.post("/v1/auth/otp/request", json={"phone_e164": "+919811111111"})).status_code == 200
    r = await client.post("/v1/auth/otp/request", json={"phone_e164": "+919811111111"})
    assert r.status_code == 429
