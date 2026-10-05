"""M4 acceptance: 50-name clipping + QC + delivery, SLA breach handling, courier tracking templates."""

import subprocess
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from config import settings
from db import SessionLocal
from models import (
    Booking,
    BookingName,
    BookingStatus,
    FakeProviderCall,
    MessageLog,
    Package,
    PujaEvent,
    Shipment,
    User,
)
from services import bookings as booking_svc
from services import events as event_svc
from services import notify, site_config, sla
from services import proof as proof_svc
from tests.conftest import book

S = BookingStatus


async def _confirmed_bookings(event_id: int, n: int) -> list[uuid.UUID]:
    ids = []
    async with SessionLocal() as db:
        ev = await db.get(PujaEvent, event_id)
        pkg = (await db.execute(select(Package).where(Package.puja_id == ev.puja_id))).scalars().first()
        for i in range(n):
            u = User(phone_e164=f"+9199{i:04d}1234", locale=["en", "hi", "ta", "te"][i % 4])
            db.add(u)
            await db.flush()
            b = await booking_svc.create_draft(db, event=ev, package=pkg, locale=u.locale, currency="INR", user=u)
            b.names.append(BookingName(booking_id=b.id, position=1, name=f"Devotee {i + 1}", gotra="Kashyapa"))
            b.consent_whatsapp_at = datetime.now(UTC)
            b.status = S.pending_payment
            await booking_svc.confirm(db, b)
            ids.append(b.id)
        await db.commit()
    return ids


def _make_video(path, seconds: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds), "-c:v", "libx264",
                    "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(path)], check=True)


async def test_fifty_name_event_each_devotee_gets_own_clip(staff_client):
    async with SessionLocal() as db:
        await site_config.set_value(db, "quiet_hours", {"start": "00:00", "end": "00:00"})
        ev = (await db.execute(select(PujaEvent).where(PujaEvent.puja_id == 1).order_by(PujaEvent.starts_at))
              ).scalars().first()
        await db.commit()
    ids = await _confirmed_bookings(ev.id, 50)

    # cutoff -> sheet; coordinator taps Started
    r = await staff_client.post(f"/v1/admin/events/{ev.id}/started")
    assert r.status_code == 200 and r.json()["notified"] == 50
    sheet = (await staff_client.get(f"/v1/admin/events/{ev.id}/sheet")).json()
    assert [row["position"] for row in sheet["rows"]] == list(range(1, 51))
    r = await staff_client.get(f"/v1/admin/events/{ev.id}/sheet.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"

    # one continuous sankalp video, 6 s per name
    key = f"events/{ev.id}/sankalp-test.mp4"
    _make_video(settings.local_media_dir / key, 50 * 6 + 5)
    async with SessionLocal() as db:
        await db.execute(update(PujaEvent).where(PujaEvent.id == ev.id).values(sankalp_video_key=key))
        await db.commit()
    markers = [{"booking_id": row["booking_id"], "start_ms": i * 6000} for i, row in enumerate(sheet["rows"])]
    assert (await staff_client.put(f"/v1/admin/events/{ev.id}/markers", json={"markers": markers})).status_code == 200
    async with SessionLocal() as db:
        ev_ = await db.get(PujaEvent, ev.id)
        assert await proof_svc.cut_event_clips(db, ev_) == 50
        await db.commit()

    clips = (await staff_client.get(f"/v1/admin/events/{ev.id}/clips")).json()
    assert len(clips["clips"]) == 50 and clips["qc"]["required_sample"] == 5
    first = clips["clips"][0]
    assert first["end_ms"] - first["start_ms"] == 8000  # next marker + 2 s

    # QC sample too small is refused
    r = await staff_client.post(f"/v1/admin/events/{ev.id}/qc-approve", json={"reviewed_ids": [first["id"]]})
    assert r.status_code == 409
    reviewed = [c["id"] for c in clips["clips"][:5]] + clips["qc"]["short_clip_ids"]
    r = await staff_client.post(f"/v1/admin/events/{ev.id}/qc-approve", json={"reviewed_ids": reviewed})
    assert r.status_code == 200 and r.json()["approved"] == 50

    async with SessionLocal() as db:
        msgs = (await db.execute(select(MessageLog).where(MessageLog.template_key == "proof_video"))).scalars().all()
    assert len(msgs) == 50
    by_booking = {m.booking_id: m for m in msgs}
    codes = {}
    async with SessionLocal() as db:
        for bid in ids:
            codes[bid] = (await db.get(Booking, bid)).code
    for bid in ids:
        m = by_booking[bid]
        assert codes[bid] in m.header_media_url  # each devotee's own clip as the header video
        assert m.header_media_url.endswith(".mp4")
        assert await notify.send_one(str(m.id)) == "sent"
    async with SessionLocal() as db:
        statuses = {(await db.get(Booking, bid)).status for bid in ids}
    assert statuses == {S.completed}  # proof sent and no shipment
    # proof page is shareable by token
    async with SessionLocal() as db:
        token = (await db.get(Booking, ids[0])).proof_token
    async with __import__("httpx").AsyncClient(transport=__import__("httpx").ASGITransport(
            app=__import__("main").app), base_url="http://test") as anon:
        p = (await anon.get(f"/v1/proof/{token}")).json()
    assert p["clip"]["url"].endswith(".mp4") and p["names"] == ["Devotee 1"]


async def test_sla_breach_alerts_ops_and_sends_proof_delayed(client):
    res = await book(client)
    bid = uuid.UUID(res["draft_id"])
    async with SessionLocal() as db:
        b = await db.get(Booking, bid)
        past = datetime.now(UTC) - timedelta(hours=60)
        await db.execute(update(PujaEvent).where(PujaEvent.id == b.puja_event_id).values(
            starts_at=past, booking_cutoff_at=past - timedelta(hours=12), video_sla_hours=48))
        await db.commit()
    async with SessionLocal() as db:
        board = await sla.board(db)
        assert board["groups"][0]["bookings"][0]["state"] == "breached"
        assert await sla.check_breaches(db) == 1
        assert await sla.check_breaches(db) == 0  # once per booking
        await db.commit()
        delayed = (await db.execute(select(MessageLog).where(MessageLog.booking_id == bid,
                                                             MessageLog.template_key == "proof_delayed"))).scalar_one()
        alerts = (await db.execute(select(FakeProviderCall).where(FakeProviderCall.kind == "alerts"))).scalars().all()
    assert delayed.params[0] and len(alerts) == 1


async def test_at_risk_six_hours_before_breach(client):
    res = await book(client)
    async with SessionLocal() as db:
        b = await db.get(Booking, uuid.UUID(res["draft_id"]))
        start = datetime.now(UTC) - timedelta(hours=44)  # due in 4 h with a 48 h SLA
        await db.execute(update(PujaEvent).where(PujaEvent.id == b.puja_event_id).values(
            starts_at=start, booking_cutoff_at=start - timedelta(hours=12), video_sla_hours=48))
        await db.commit()
        board = await sla.board(db)
    assert board["groups"][0]["bookings"][0]["state"] == "at_risk"


async def test_courier_events_move_shipment_and_send_three_templates(client, staff_client):
    res = await book(client, puja_id=4, prasad=True)
    bid = uuid.UUID(res["draft_id"])
    async with SessionLocal() as db:
        b = await db.get(Booking, bid)
        event_id = b.puja_event_id
    r = await staff_client.post(f"/v1/admin/shipping/events/{event_id}/bulk-create")
    assert r.status_code == 200 and len(r.json()["created"]) == 1
    async with SessionLocal() as db:
        sh = (await db.execute(select(Shipment).where(Shipment.booking_id == bid))).scalar_one()
    assert sh.awb and sh.status.value == "packed"
    for i, status in enumerate(["shipped", "out_for_delivery", "out_for_delivery", "delivered"]):
        r = await client.post("/v1/webhooks/shipping/fake", headers={"x-fake-token": "fake-token"},
                              json={"event_id": f"e{i}", "awb": sh.awb, "status": status})
        assert r.status_code == 200
    async with SessionLocal() as db:
        sh = (await db.execute(select(Shipment).where(Shipment.booking_id == bid))).scalar_one()
        keys = [m.template_key for m in (await db.execute(
            select(MessageLog).where(MessageLog.booking_id == bid, MessageLog.template_key.like("prasad_%"))
            .order_by(MessageLog.created_at))).scalars()]
    assert sh.status.value == "delivered"
    assert keys == ["prasad_shipped", "prasad_out_for_delivery", "prasad_delivered"]


async def test_disrupted_event_reschedule_accept_and_refund(client, staff_client):
    r1 = await book(client, phone="+919876543210")
    async with SessionLocal() as db:
        b = await db.get(Booking, uuid.UUID(r1["draft_id"]))
        ev_id = b.puja_event_id
    new_start = (datetime.now(UTC) + timedelta(days=20)).replace(microsecond=0).isoformat()
    r = await staff_client.post(f"/v1/admin/events/{ev_id}/disrupt",
                                json={"action": "reschedule", "new_starts_at": new_start})
    assert r.status_code == 200 and r.json()["rescheduled"] == 1
    async with SessionLocal() as db:
        b = await db.get(Booking, b.id)
        assert b.status == S.rescheduled
    # devotee taps Refund on the WhatsApp quick reply
    await client.post("/v1/dev/fake-messaging-event", json={"kind": "inbound_button", "from_": "+919876543210",
                                                            "button": "Refund"})
    async with SessionLocal() as db:
        b = await db.get(Booking, b.id)
    assert b.status == S.cancelled and b.cancel_reason == "reschedule_refund"


async def test_unanswered_reschedule_defaults_to_accept(client, staff_client):
    r1 = await book(client)
    async with SessionLocal() as db:
        b = await db.get(Booking, uuid.UUID(r1["draft_id"]))
    new_start = (datetime.now(UTC) + timedelta(days=20)).replace(microsecond=0).isoformat()
    await staff_client.post(f"/v1/admin/events/{b.puja_event_id}/disrupt",
                            json={"action": "reschedule", "new_starts_at": new_start})
    async with SessionLocal() as db:
        await db.execute(update(Booking).values(reschedule_deadline_at=datetime.now(UTC) - timedelta(minutes=1)))
        await db.commit()
        assert await event_svc.auto_accept_reschedules(db) == 1
        await db.commit()
        b2 = await db.get(Booking, b.id)
    assert b2.status == S.confirmed and b2.puja_event_id != b.puja_event_id


def test_transliteration_into_sankalp_script():
    assert event_svc.transliterate("Ramesh", "Sanskrit") == "रमेश"
    assert event_svc.transliterate("Lakshmi", "Telugu").startswith("ల")
    assert event_svc.transliterate("ரமேஷ்", "Tamil") == "ரமேஷ்"
    assert event_svc.transliterate("Ravi", "English") == "Ravi"
