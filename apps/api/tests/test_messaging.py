"""M3 acceptance: idempotent sends, retries, quiet hours, status webhooks, consent; WATI + Gupshup adapters."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from sqlalchemy import func, select

from db import SessionLocal
from models import Booking, FakeProviderCall, MessageLog, MessageStatus, User
from providers.messaging.base import TemplateRef
from providers.messaging.gupshup import GupshupProvider
from providers.messaging.wati import WatiProvider
from services import notify, site_config
from services.i18n import in_quiet_hours, tz_for_phone
from tests.conftest import book

NO_QUIET = {"start": "00:00", "end": "00:00"}


async def _no_quiet_hours():
    async with SessionLocal() as db:
        await site_config.set_value(db, "quiet_hours", NO_QUIET)
        await db.commit()


async def _msg(booking_id, key) -> MessageLog:
    async with SessionLocal() as db:
        return (await db.execute(select(MessageLog).where(MessageLog.booking_id == booking_id,
                                                          MessageLog.template_key == key))).scalar_one()


async def test_booking_confirmed_sent_once_even_when_forced_to_retry(client):
    await _no_quiet_hours()
    res = await book(client)
    bid = uuid.UUID(res["draft_id"])
    m = await _msg(bid, "booking_confirmed")
    assert await notify.send_one(str(m.id)) == "sent"
    # forced retries of the same job, and re-queueing the same (booking, template, occurrence)
    assert (await notify.send_one(str(m.id))).startswith("skip")
    assert (await notify.send_one(str(m.id))).startswith("skip")
    async with SessionLocal() as db:
        b = await db.get(Booking, bid)
        assert await notify.queue(db, template_key="booking_confirmed", to=b.whatsapp_e164, locale="en",
                                  booking=b, params=["x"]) is None
        await db.commit()
        sends = (await db.execute(select(func.count()).select_from(FakeProviderCall).where(
            FakeProviderCall.method == "send_template",
            FakeProviderCall.payload["template"].astext == "booking_confirmed"))).scalar()
    assert sends == 1
    m = await _msg(bid, "booking_confirmed")
    assert m.status == MessageStatus.sent and m.provider_message_id


async def test_timeouts_retry_with_backoff_then_fail(client):
    await _no_quiet_hours()
    res = await book(client, phone="+919800000002")  # fake provider: simulated timeout
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    delays = []
    for _ in range(4):
        outcome = await notify.send_one(str(m.id))
        m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
        delays.append(m.scheduled_for)
        async with SessionLocal() as db:  # make it due again
            row = await db.get(MessageLog, m.id)
            row.scheduled_for = datetime.now(UTC) - timedelta(seconds=1)
            await db.commit()
    assert outcome == "failed" and m.status == MessageStatus.failed and m.attempts == 4


async def test_invalid_number_goes_to_ops_call_queue(client):
    await _no_quiet_hours()
    res = await book(client, phone="+919800000001")
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    assert await notify.send_one(str(m.id)) == "rejected"
    async with SessionLocal() as db:
        b = await db.get(Booking, uuid.UUID(res["draft_id"]))
    assert b.needs_call_reason == "whatsapp_invalid_number"


def test_quiet_hours_window():
    ist = tz_for_phone("+919876543210")
    quiet = {"start": "21:30", "end": "07:30"}
    late = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)  # 22:30 IST
    resume = in_quiet_hours(late, ist, quiet)
    assert resume == datetime(2026, 10, 6, 2, 0, tzinfo=UTC)  # 07:30 IST next day
    assert in_quiet_hours(datetime(2026, 10, 5, 6, 0, tzinfo=UTC), ist, quiet) is None  # 11:30 IST
    # recipient time zone, not the server's: 22:30 IST is 13:00 in New York
    assert in_quiet_hours(late, tz_for_phone("+12125550100"), quiet) is None


async def test_quiet_hours_hold_utility_but_not_otp(client):
    async with SessionLocal() as db:
        await site_config.set_value(db, "quiet_hours", {"start": "00:00", "end": "23:59"})
        await db.commit()
    res = await book(client)
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    assert await notify.send_one(str(m.id)) == "held"
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    assert m.status == MessageStatus.queued and m.scheduled_for > datetime.now(UTC)
    async with SessionLocal() as db:
        otp = (await db.execute(select(MessageLog).where(MessageLog.template_key == "otp_login"))).scalars().first()
    assert await notify.send_one(str(otp.id)) == "sent"


async def test_status_webhooks_update_log_and_never_go_backwards(client):
    await _no_quiet_hours()
    res = await book(client)
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    await notify.send_one(str(m.id))
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    for kind in ("delivered", "read", "delivered"):
        r = await client.post("/v1/dev/fake-messaging-event", json={"kind": kind, "id": m.provider_message_id})
        assert r.status_code == 200
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    assert m.status == MessageStatus.read and m.delivered_at and m.read_at


async def test_stop_removes_marketing_consent_and_blocks_marketing(client):
    await _no_quiet_hours()
    await book(client)
    async with SessionLocal() as db:
        u = (await db.execute(select(User))).scalars().first()
        u.marketing_opt_in_at = datetime.now(UTC)
        await db.commit()
    await client.post("/v1/dev/fake-messaging-event", json={"kind": "inbound_text", "from_": u.phone_e164,
                                                            "text": "STOP"})
    async with SessionLocal() as db:
        u = await db.get(User, u.id)
        assert u.marketing_opt_in_at is None
        mid = await notify.queue(db, template_key="festival_offer", to=u.phone_e164, locale="en", user_id=u.id,
                                 params=["Diwali", "Lakshmi Puja"], occurrence_key="t")
        await db.commit()
    assert await notify.send_one(str(mid)) == "no_consent"


async def test_inbound_logged_against_latest_booking(client):
    res = await book(client)
    await client.post("/v1/dev/fake-messaging-event", json={"kind": "inbound_text", "from_": "+919876543210",
                                                            "text": "When is my puja?"})
    async with SessionLocal() as db:
        from models import InboundMessage

        m = (await db.execute(select(InboundMessage))).scalar_one()
    assert str(m.matched_booking_id) == res["draft_id"]


# ---------------------------------------------------------------- adapters: same suite for WATI and Gupshup
def _wati():
    return WatiProvider("https://live-server.wati.io/123", "tok", "hook-secret")


def _gupshup():
    return GupshupProvider("key", "PujaPathApp", "+919000000000", "hook-secret")


ADAPTERS = {"wati": _wati, "gupshup": _gupshup}
TPL = TemplateRef("booking_confirmed", "te", "ref-1", ["name", "puja", "temple", "datetime_ist", "package", "code"])


@pytest.mark.parametrize("name", ["wati", "gupshup"])
@respx.mock
async def test_adapter_send_template(name):
    p = ADAPTERS[name]()
    if name == "wati":
        route = respx.post("https://live-server.wati.io/123/api/v2/sendTemplateMessage").mock(
            return_value=httpx.Response(200, json={"result": True, "localMessageId": "wati-1"}))
    else:
        route = respx.post("https://api.gupshup.io/wa/api/v1/template/msg").mock(
            return_value=httpx.Response(202, json={"status": "submitted", "messageId": "gs-1"}))
    res = await p.send_template("+919876543210", TPL, ["Ravi", "Puja", "Temple", "1 Jan", "Individual", "ABC123"],
                                header_media_url="https://cdn.example/clip.mp4", button_params=["te/proof/x"],
                                idempotency_key="k1")
    assert res.accepted and res.provider_message_id in ("wati-1", "gs-1")
    req = route.calls.last.request
    if name == "wati":
        assert req.url.params["whatsappNumber"] == "919876543210"
        assert req.headers["authorization"] == "Bearer tok"
        body = json.loads(req.content)
        assert body["template_name"] == "ref-1"
        assert {"name": "name", "value": "Ravi"} in body["parameters"]
    else:
        assert req.headers["apikey"] == "key"
        form = dict(x.split("=", 1) for x in req.content.decode().split("&"))
        assert form["destination"] == "919876543210" and form["source"] == "919000000000"
        tpl = json.loads(httpx.QueryParams(req.content.decode())["template"])
        assert tpl["id"] == "ref-1" and tpl["params"][0] == "Ravi"
        assert "video" in httpx.QueryParams(req.content.decode())["message"]


@pytest.mark.parametrize("name", ["wati", "gupshup"])
@respx.mock
async def test_adapter_retryable_on_5xx(name):
    from providers.errors import RetryableProviderError

    p = ADAPTERS[name]()
    url = ("https://live-server.wati.io/123/api/v2/sendTemplateMessage" if name == "wati"
           else "https://api.gupshup.io/wa/api/v1/template/msg")
    respx.post(url).mock(return_value=httpx.Response(503))
    with pytest.raises(RetryableProviderError):
        await p.send_template("+919876543210", TPL, ["a"] * 6)


@pytest.mark.parametrize("name", ["wati", "gupshup"])
def test_adapter_parses_status_and_inbound_webhooks(name):
    p = ADAPTERS[name]()
    h = {"x-webhook-token": "hook-secret"}
    if name == "wati":
        payloads = [{"eventType": "sentMessageDELIVERED_v2", "localMessageId": "m1"},
                    {"eventType": "sentMessageREAD_v2", "localMessageId": "m1"},
                    {"eventType": "templateMessageFailed", "localMessageId": "m2", "failedCode": "131026"},
                    {"eventType": "messageReceived", "waId": "919876543210", "text": "STOP", "type": "text"},
                    {"eventType": "messageReceived", "waId": "919876543210", "type": "button",
                     "buttonReply": {"payload": "Accept", "text": "Accept"}}]
    else:
        payloads = [{"type": "message-event", "payload": {"type": "delivered", "gsId": "m1"}},
                    {"type": "message-event", "payload": {"type": "read", "gsId": "m1"}},
                    {"type": "message-event", "payload": {"type": "failed", "gsId": "m2",
                                                          "payload": {"code": 131026}}},
                    {"type": "message", "payload": {"type": "text", "sender": {"phone": "919876543210"},
                                                    "payload": {"text": "STOP"}}},
                    {"type": "message", "payload": {"type": "quick_reply", "sender": {"phone": "919876543210"},
                                                    "payload": {"text": "Accept", "postbackText": "Accept"}}}]
    events = [e for pl in payloads for e in p.parse_webhook(h, json.dumps(pl).encode())]
    assert [e.kind for e in events] == ["delivered", "read", "failed", "inbound_text", "inbound_button"]
    assert events[0].provider_message_id == "m1" and events[2].error_code == "131026"
    assert events[3].from_e164 == "+919876543210" and events[3].text == "STOP"
    assert events[4].button_payload == "Accept"


@pytest.mark.parametrize("name", ["wati", "gupshup"])
def test_adapter_rejects_bad_webhook_token(name):
    from providers.errors import WebhookVerificationError

    with pytest.raises(WebhookVerificationError):
        ADAPTERS[name]().parse_webhook({"x-webhook-token": "wrong"}, b"{}")


@pytest.mark.parametrize("name", ["wati", "gupshup"])
@respx.mock
async def test_adapter_lists_templates(name):
    p = ADAPTERS[name]()
    if name == "wati":
        respx.get("https://live-server.wati.io/123/api/v1/getMessageTemplates").mock(return_value=httpx.Response(
            200, json={"messageTemplates": [{"elementName": "pp_booking_confirmed_te", "status": "APPROVED",
                                             "category": "UTILITY", "language": {"value": "te"}}]}))
    else:
        respx.get("https://api.gupshup.io/sm/api/v1/template/list/PujaPathApp").mock(return_value=httpx.Response(
            200, json={"templates": [{"id": "uuid-1", "elementName": "pp_booking_confirmed_te",
                                      "languageCode": "te", "status": "APPROVED", "category": "UTILITY"}]}))
    t = (await p.list_templates())[0]
    assert t.name == "pp_booking_confirmed_te" and t.status == "approved"


@pytest.mark.parametrize("name", ["wati", "gupshup"])
async def test_end_to_end_through_real_adapter(name, client, monkeypatch):
    """MESSAGING_PROVIDER=<name>: booking -> send via the adapter's HTTP API -> status webhook -> delivered."""
    from config import settings

    await _no_quiet_hours()
    monkeypatch.setattr(settings, "messaging_provider", name)
    monkeypatch.setattr(settings, "wati_api_endpoint", "https://live-server.wati.io/123")
    monkeypatch.setattr(settings, "wati_access_token", "tok")
    monkeypatch.setattr(settings, "wati_webhook_token", "hook-secret")
    monkeypatch.setattr(settings, "gupshup_api_key", "key")
    monkeypatch.setattr(settings, "gupshup_app_name", "PujaPathApp")
    monkeypatch.setattr(settings, "gupshup_source_number", "+919000000000")
    monkeypatch.setattr(settings, "gupshup_webhook_token", "hook-secret")
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as mock:
        mock.route(host="test").pass_through()
        mock.post("https://live-server.wati.io/123/api/v2/sendTemplateMessage").mock(
            return_value=httpx.Response(200, json={"result": True, "localMessageId": "prov-1"}))
        mock.post("https://api.gupshup.io/wa/api/v1/template/msg").mock(
            return_value=httpx.Response(202, json={"status": "submitted", "messageId": "prov-1"}))
        res = await book(client)
        m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
        assert m.provider == name
        assert await notify.send_one(str(m.id)) == "sent"
    status = ({"eventType": "sentMessageDELIVERED_v2", "localMessageId": "prov-1"} if name == "wati"
              else {"type": "message-event", "payload": {"type": "delivered", "gsId": "prov-1"}})
    r = await client.post(f"/v1/webhooks/messaging/{name}?token=hook-secret", json=status)
    assert r.status_code == 200
    m = await _msg(uuid.UUID(res["draft_id"]), "booking_confirmed")
    assert m.status == MessageStatus.delivered
    r = await client.post(f"/v1/webhooks/messaging/{name}?token=bad", json=status)
    assert r.status_code == 401


async def test_unapproved_language_falls_back_to_english_template():
    from models import MessageTemplate

    async with SessionLocal() as db:
        # Seeded rows for real providers start as "pending" until Sync templates marks them approved.
        en = await db.get(MessageTemplate, ("booking_confirmed", "en", "wati"))
        hi = await db.get(MessageTemplate, ("booking_confirmed", "hi", "wati"))
        assert hi.status == "pending"
        en.status = "approved"
        await db.commit()
        ref = await notify._template_ref(db, "booking_confirmed", "hi", "wati")
        assert (ref.locale, ref.provider_ref) == ("en", "pp_booking_confirmed_en")

        hi.status = "approved"
        await db.commit()
        ref = await notify._template_ref(db, "booking_confirmed", "hi", "wati")
        assert (ref.locale, ref.provider_ref) == ("hi", "pp_booking_confirmed_hi")


@respx.mock
async def test_telnyx_sms_otp_sends_localized_code(monkeypatch):
    from config import settings
    from providers.sms import send_sms_otp

    monkeypatch.setattr(settings, "sms_otp_provider", "telnyx")
    monkeypatch.setattr(settings, "sms_otp_api_key", "KEY123")
    monkeypatch.setattr(settings, "sms_otp_from", "+15550001111")
    route = respx.post("https://api.telnyx.com/v2/messages").mock(return_value=httpx.Response(200, json={"data": {}}))
    await send_sms_otp("+919876543210", "482913", "hi")
    sent = json.loads(route.calls[0].request.content)
    assert route.calls[0].request.headers["authorization"] == "Bearer KEY123"
    assert sent["to"] == "+919876543210" and sent["from"] == "+15550001111"
    assert "482913" in sent["text"] and "सत्यापन" in sent["text"]


def test_templates_meet_meta_rules():
    """Meta rejects bodies that start or end with a variable, and button labels over 25 characters."""
    import re
    import sys
    from pathlib import Path

    from services.messaging_templates import TEMPLATE_SPECS

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from create_templates import payload

    for key, spec in TEMPLATE_SPECS.items():
        for locale, body in spec["body"].items():
            if spec["category"] != "authentication":
                assert not re.match(r"^\{\{\d+\}\}", body.strip()), (key, locale)
                assert not re.search(r"\{\{\d+\}\}\W?$", body.strip()), (key, locale)
            for fmt in ("named", "positional"):
                p = payload(key, locale, "https://example.com", fmt, "handle")
                assert p["name"] == f"pp_{key}_{locale}"
                for c in p["components"]:
                    for b in c.get("buttons", []):
                        assert len(b.get("text", "")) <= 25, (key, locale, b)
