"""Development-only helpers for the fake providers. Mounted only when APP_ENV is development/test."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from models import FakeProviderCall, Payment
from providers.payments.fake import FakePaymentProvider
from routers.webhooks import process_payment_body

router = APIRouter(prefix="/v1/dev", tags=["dev"])


class FakePayIn(BaseModel):
    outcome: str = "success"  # success | failure


@router.post("/fake-gateway/{order_id}")
async def fake_gateway(order_id: str, body: FakePayIn, db: AsyncSession = Depends(get_db)):
    """What a real gateway does after the devotee pays: send us a signed webhook."""
    pay = (await db.execute(select(Payment).where(Payment.provider_order_id == order_id))).scalar_one_or_none()
    if pay is None or pay.provider != "fake":
        raise HTTPException(404, "unknown_order")
    event = {"kind": "payment_captured" if body.outcome == "success" else "payment_failed",
             "order_id": order_id, "payment_id": f"fake_pay_{uuid.uuid4().hex[:12]}",
             "amount_minor": pay.amount_minor, "currency": pay.currency}
    if pay.raw and pay.raw.get("mandate_ref"):
        event["mandate_token"] = pay.raw["mandate_ref"]
    return await deliver(event)


async def deliver(event: dict) -> dict:
    provider = FakePaymentProvider(settings.fake_payment_webhook_secret)
    headers, raw = provider.build_webhook(**event)
    return await process_payment_body("fake", headers, raw)


@router.get("/fake-calls")
async def fake_calls(kind: str | None = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(FakeProviderCall).order_by(FakeProviderCall.id.desc()).limit(limit)
    if kind:
        stmt = stmt.where(FakeProviderCall.kind == kind)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": r.id, "kind": r.kind, "method": r.method, "payload": r.payload,
             "at": r.created_at.isoformat()} for r in rows]


class FakeMessagingEvent(BaseModel):
    kind: str
    id: str | None = None
    from_: str | None = None
    text: str | None = None
    button: str | None = None
    code: str | None = None


@router.post("/fake-messaging-event")
async def fake_messaging_event(body: FakeMessagingEvent):
    """Simulates a BSP callback (delivered/read/inbound) for local testing."""
    from starlette.requests import Request

    from routers.webhooks import messaging_webhook

    payload = json.dumps({"kind": body.kind, "id": body.id, "from": body.from_, "text": body.text,
                          "button": body.button, "code": body.code}).encode()
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [(b"x-fake-token", b"fake-token")],
             "query_string": b""}

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    return await messaging_webhook("fake", Request(scope, receive))
