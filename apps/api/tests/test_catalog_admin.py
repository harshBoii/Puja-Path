"""M1 acceptance (API side): publishing rules, per-locale catalogs, cutoff, countdown; staff auth, roles, audit."""

from datetime import UTC, datetime, timedelta

import pyotp
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from db import SessionLocal
from models import AuditLog, PujaEvent
from security import hash_password

TEMPLE = 1


async def _new_puja(staff, **over):
    body = {"temple_id": TEMPLE, "kind": "one_time", "tradition": "Shaiva Agama", "duration_minutes": 60,
            "priests_count": 2, "sankalp_language": "Sanskrit", "deliverables": ["sankalp_clip", "full_video"],
            "images": [{"key": "/images/seed/lotus.svg", "alt": {"en": "Lotus", "te": "కమలం"}}], **over}
    p = (await staff.post("/v1/admin/pujas", json=body)).json()
    await staff.put(f"/v1/admin/pujas/{p['id']}/packages", json=[
        {"code": "individual", "max_names": 1, "price_inr_minor": 50100, "price_usd_minor": 1500}])
    return p


def _tr(**over):
    return {"title": "Pradosha Puja", "subtitle": "Evening worship on Trayodashi", "occasion_chip": "Pradosham",
            "about_md": "Pradosha puja is offered at twilight.", "benefits": [{"title": "Purpose", "line": "Worship."}],
            "rituals": [{"title": "Abhishekam", "text": "With milk.", "main": True}], "faqs": [],
            "meta_title": "Pradosha Puja", "meta_description": "Book Pradosha Puja.", **over}


async def test_publish_in_two_locales_appears_in_both(staff_client, client):
    p = await _new_puja(staff_client)
    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/en", json=_tr())
    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/te", json=_tr(
        title="ప్రదోష పూజ", subtitle="త్రయోదశి సాయంత్రం పూజ", occasion_chip="ప్రదోషం", about_md="సంధ్యా సమయంలో.",
        meta_title="ప్రదోష పూజ", meta_description="ప్రదోష పూజ బుక్ చేయండి.",
        benefits=[{"title": "ఉద్దేశం", "line": "ఆరాధన."}], rituals=[{"title": "అభిషేకం", "text": "పాలతో.", "main": True}]))
    start = (datetime.now(UTC) + timedelta(days=5)).replace(microsecond=0, tzinfo=None).isoformat()
    assert (await staff_client.post("/v1/admin/events", json={"puja_id": p["id"], "starts_at": start})).status_code == 201
    r = await staff_client.post(f"/v1/admin/pujas/{p['id']}/publish", json={"locales": ["en", "te"]})
    assert r.status_code == 200, r.text
    for loc in ("en", "te"):
        ids = [i["id"] for i in (await client.get(f"/v1/{loc}/pujas?limit=48")).json()["items"]]
        assert p["id"] in ids
    assert p["id"] not in [i["id"] for i in (await client.get("/v1/hi/pujas?limit=48")).json()["items"]]
    assert (await client.get(f"/v1/hi/pujas/{p['id']}")).status_code == 404


async def test_publish_blocked_on_empty_meta_placeholder_and_banned_phrase(staff_client):
    p = await _new_puja(staff_client)
    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/en", json=_tr(meta_description=""))
    r = await staff_client.post(f"/v1/admin/pujas/{p['id']}/publish", json={"locales": ["en"]})
    assert r.status_code == 422
    assert {"locale": "en", "field": "meta_description", "code": "required"} in r.json()["detail"]["errors"]

    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/en",
                           json=_tr(about_md="Performed daily (Adjust per policy). TODO add history"))
    errs = (await staff_client.post(f"/v1/admin/pujas/{p['id']}/publish", json={"locales": ["en"]})).json()
    assert any(e["code"] == "placeholder" for e in errs["detail"]["errors"])

    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/en",
                           json=_tr(subtitle="Guaranteed victory in court cases"))
    errs = (await staff_client.post(f"/v1/admin/pujas/{p['id']}/publish", json={"locales": ["en"]})).json()
    assert any(e["code"].startswith("banned_phrase") for e in errs["detail"]["errors"])

    # template variable: no Hindi temple name -> the WhatsApp templates would render empty
    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/en", json=_tr())
    errs = (await staff_client.post(f"/v1/admin/pujas/{p['id']}/validate", json={"locales": ["en"]})).json()
    assert errs["errors"] == []


async def test_required_facts_have_no_defaults(staff_client):
    p = await _new_puja(staff_client, tradition="", priests_count=0)
    await staff_client.put(f"/v1/admin/pujas/{p['id']}/translations/en", json=_tr())
    errs = (await staff_client.post(f"/v1/admin/pujas/{p['id']}/validate", json={"locales": ["en"]})).json()["errors"]
    fields = {e["field"] for e in errs}
    assert {"tradition", "priests_count"} <= fields


async def test_puja_leaves_listing_at_cutoff(client):
    async with SessionLocal() as db:
        await db.execute(update(PujaEvent).where(PujaEvent.puja_id == 5).values(
            booking_cutoff_at=datetime.now(UTC) - timedelta(minutes=1)))
        await db.commit()
    ids = [i["id"] for i in (await client.get("/v1/en/pujas?limit=48")).json()["items"]]
    assert 5 not in ids


async def test_countdown_only_for_real_cutoff_under_72h(client):
    async with SessionLocal() as db:
        events = (await db.execute(select(PujaEvent).order_by(PujaEvent.booking_cutoff_at))).scalars().all()
    for ev in events:
        data = (await client.get(f"/v1/events/{ev.id}/countdown")).json()
        remaining = (ev.booking_cutoff_at - datetime.now(UTC)).total_seconds()
        assert data["show"] == (0 < remaining < 72 * 3600)


async def test_listing_filters_sort_search_and_pagination(client):
    r = (await client.get("/v1/en/pujas?dosha=navagraha")).json()
    assert r["items"] and all("navagraha" in i["dosha_tags"] for i in r["items"])
    prices = [i["from_price_minor"] for i in (await client.get("/v1/en/pujas?sort=price")).json()["items"]]
    assert prices == sorted(prices)
    assert (await client.get("/v1/te/pujas?q=రుద్ర")).json()["total"] >= 1
    page = (await client.get("/v1/en/pujas?limit=2&offset=0")).json()
    assert len(page["items"]) == 2 and page["total"] >= 6
    usd = (await client.get("/v1/en/pujas/1?currency=USD")).json()
    assert usd["currency"] == "USD" and usd["packages"][0]["price_minor"] == 1500


async def test_staff_login_is_password_only_by_default():
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/admin/auth/login", json={"email": "admin@test.local", "password": "wrong-password"})
        assert r.status_code == 401
        r = await c.post("/v1/admin/auth/login", json={"email": "admin@test.local", "password": "test-admin-password"})
        assert r.json()["step"] == "done"
        assert (await c.get("/v1/admin/today")).status_code == 200


async def test_staff_login_requires_totp_when_enabled_and_roles_are_enforced(monkeypatch):
    from config import settings
    from main import app
    from models import StaffRole, StaffUser

    monkeypatch.setattr(settings, "staff_2fa", True)
    async with SessionLocal() as db:
        db.add(StaffUser(email="ops@test.local", name="Ops", role=StaffRole.ops_coordinator,
                         password_hash=hash_password("ops-password-123"), active=True))
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/admin/auth/login", json={"email": "ops@test.local", "password": "ops-password-123"})
        assert r.json()["step"] == "enroll_totp"
        assert (await c.get("/v1/admin/today")).status_code == 401  # password alone is not a session
        assert (await c.post("/v1/admin/auth/totp", json={"code": "000000"})).status_code == 401
        assert (await c.post("/v1/admin/auth/totp", json={"code": "12345"})).status_code == 401
        code = pyotp.TOTP(r.json()["secret"]).now()
        # Pasted from an authenticator app, with its display space.
        assert (await c.post("/v1/admin/auth/totp", json={"code": f" {code[:3]} {code[3:]} "})).status_code == 200
        assert (await c.get("/v1/admin/today")).status_code == 200
        assert (await c.get("/v1/admin/finance/payments")).status_code == 403
        assert (await c.get("/v1/admin/config")).status_code == 403


async def test_every_admin_write_is_audited(staff_client):
    r = await staff_client.put("/v1/admin/config/video_sla_hours_default", json={"value": 36})
    assert r.status_code == 200
    async with SessionLocal() as db:
        row = (await db.execute(select(AuditLog).where(AuditLog.action == "config.update"))).scalar_one()
    assert row.diff == {"before": 48, "after": 36}
    assert (await staff_client.get("/v1/config")).json()["video_sla_hours_default"] == 36


async def test_admin_paths_are_not_captured_by_locale_routes(staff_client):
    assert (await staff_client.get("/v1/admin/pujas/1")).status_code == 200
    assert (await staff_client.get("/v1/admin/temples")).status_code == 200
