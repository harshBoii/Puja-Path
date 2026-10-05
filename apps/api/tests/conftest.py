"""Test harness: a real Postgres (TEST_DATABASE_URL), fake providers, no network.

Every test starts from a freshly seeded catalog so tests stay independent.
"""

import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL",
                                            "postgresql://postgres@localhost:55432/pujapath_test")
os.environ["APP_ENV"] = "test"
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
for k in ("MESSAGING_PROVIDER", "PAYMENT_PROVIDER", "SHIPPING_PROVIDER", "SMS_OTP_PROVIDER"):
    os.environ[k] = "fake"
os.environ["WEB_INTERNAL_URL"] = "http://127.0.0.1:9"  # revalidation calls fail fast and are ignored
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"

import asyncio  # noqa: E402

import pyotp  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from config import API_DIR  # noqa: E402
from db import SessionLocal, engine  # noqa: E402

_migrated = False


async def _migrate() -> None:
    global _migrated
    if not _migrated:
        cfg = Config(str(API_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_DIR / "migrations"))
        # alembic's env.py calls asyncio.run(); keep it off the test loop
        await asyncio.to_thread(command.upgrade, cfg, "head")
        _migrated = True


@pytest.fixture(autouse=True)
async def fresh_db():
    import seed

    await _migrate()
    async with engine.begin() as conn:
        tables = (await conn.execute(text(
            "select tablename from pg_tables where schemaname='public' and tablename <> 'alembic_version'"
        ))).scalars().all()
        await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    async with SessionLocal() as db:
        await seed.seed_base(db)
        await seed.seed_catalog(db)
    yield


@pytest.fixture
async def client():
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def staff_client():
    """Logged-in admin (password + TOTP)."""
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/v1/admin/auth/login", json={"email": "admin@test.local", "password": "test-admin-password"})
        assert r.status_code == 200, r.text
        secret = r.json()["secret"]
        r = await c.post("/v1/admin/auth/totp", json={"code": pyotp.TOTP(secret).now()})
        assert r.status_code == 200, r.text
        yield c


async def login(client: AsyncClient, phone: str) -> None:
    r = await client.post("/v1/auth/otp/request", json={"phone_e164": phone})
    assert r.status_code == 200, r.text
    r = await client.post("/v1/auth/otp/verify", json={"phone_e164": phone, "code": r.json()["dev_code"]})
    assert r.status_code == 200, r.text


async def book(client: AsyncClient, *, puja_id: int = 1, package: str = "individual", phone: str = "+919876543210",
               names: list[dict] | None = None, prasad: bool = False, locale: str = "en", pay: bool = True,
               nakshatra: str | None = None) -> dict:
    """Runs Journey A through the API: detail -> draft -> sankalp -> OTP login -> pay -> signed webhook."""
    detail = (await client.get(f"/v1/{locale}/pujas/{puja_id}")).json()
    pkg = next(p for p in detail["packages"] if p["code"] == package)
    r = await client.post("/v1/drafts", json={"puja_id": puja_id, "package_id": pkg["id"], "locale": locale})
    assert r.status_code == 201, r.text
    draft_id = r.json()["id"]
    names = names or [{"name": "Lakshmi Devi", "gotra": "Bharadwaja", "nakshatra": nakshatra}]
    body = {"names": names, "whatsapp_e164": phone, "consent_whatsapp": True, "wish": "Good health"}
    if prasad:
        body.update({"prasad": True, "address": {"name": "Lakshmi", "phone": "+919876543210", "line1": "12 Temple St",
                                                 "city": "Hyderabad", "state": "Telangana", "pincode": "500001"}})
    r = await client.put(f"/v1/drafts/{draft_id}", json=body)
    assert r.status_code == 200, r.text
    view = r.json()
    if not pay:
        return {"draft_id": draft_id, "view": view}
    await login(client, phone)
    r = await client.post(f"/v1/drafts/{draft_id}/pay", json={
        "consent_terms": True, "expected_total_minor": view["pricing"]["total_minor"]})
    assert r.status_code == 200, r.text
    order_id = r.json()["checkout"]["order_id"]
    r = await client.post(f"/v1/dev/fake-gateway/{order_id}", json={"outcome": "success"})
    assert r.status_code == 200, r.text
    return {"draft_id": draft_id, "order_id": order_id, "view": view}
