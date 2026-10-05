"""Inbound webhooks. Each is signature/token-verified, stored in webhook_events (unique idempotency key),
then processed. Replays of the same event are acknowledged and skipped."""

import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from db import SessionLocal
from logging_setup import log
from models import WebhookEvent
from providers.errors import WebhookVerificationError
from providers.messaging import get_messaging_provider
from providers.payments import get_payment_provider
from providers.shipping import get_shipping_provider
from services import bookings as booking_svc
from services import notify
from services import shipping as shipping_svc
from services.i18n import utcnow

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
logger = logging.getLogger("webhooks")


def _headers(request: Request) -> dict:
    h = {k.lower(): v for k, v in request.headers.items()}
    if "token" in request.query_params:  # WATI/Gupshup callbacks carry our shared token in the URL
        h["x-webhook-token"] = request.query_params["token"]
    return h


async def _claim(provider: str, event_type: str, key: str, payload: dict) -> WebhookEvent | None:
    """Inserts the event; returns None if this key was already processed (replay)."""
    async with SessionLocal() as db:
        stmt = insert(WebhookEvent).values(provider=provider, event_type=event_type, idempotency_key=key,
                                           payload=payload).on_conflict_do_nothing(index_elements=["idempotency_key"])
        await db.execute(stmt)
        await db.commit()
        row = (await db.execute(select(WebhookEvent).where(WebhookEvent.idempotency_key == key))).scalar_one()
        return None if row.processed_at else row


async def _done(row_id, error: str | None = None) -> None:
    async with SessionLocal() as db:
        row = await db.get(WebhookEvent, row_id)
        if error:
            row.error = error[:2000]
        else:
            row.processed_at, row.error = utcnow(), None
        await db.commit()


async def process_payment_body(provider_name: str, headers: dict, body: bytes) -> dict:
    provider = get_payment_provider(provider_name)
    try:
        events = provider.verify_webhook(headers, body)
    except WebhookVerificationError as e:
        raise HTTPException(401, "bad_signature") from e
    processed = 0
    for ev in events:
        row = await _claim(f"payments:{provider.name}", ev.kind, f"{provider.name}:{ev.event_id}", ev.raw)
        if row is None:
            continue
        async with SessionLocal() as db:
            try:
                # Serialise per order so concurrent replays cannot both confirm.
                if ev.order_id:
                    await db.execute(select(1).where(WebhookEvent.id == row.id).with_for_update())
                await booking_svc.on_payment_event(db, ev, provider.name)
                await notify.commit_and_dispatch(db)
            except Exception as e:
                await db.rollback()
                await _done(row.id, error=repr(e))
                log(logger, "payment webhook failed", event=ev.kind, error=repr(e))
                raise HTTPException(500, "processing_failed") from e
        await _done(row.id)
        processed += 1
        log(logger, "payment webhook", provider=provider.name, kind=ev.kind, order_id=ev.order_id)
    return {"ok": True, "processed": processed}


@router.post("/payments/{provider_name}")
async def payments_webhook(provider_name: str, request: Request):
    from config import settings

    if provider_name != settings.payment_provider and provider_name != "fake":
        raise HTTPException(404, "unknown_provider")
    return await process_payment_body(provider_name, _headers(request), await request.body())


@router.post("/messaging/{provider_name}")
async def messaging_webhook(provider_name: str, request: Request):
    provider = get_messaging_provider(provider_name)
    body = await request.body()
    try:
        events = provider.parse_webhook(_headers(request), body)
    except WebhookVerificationError as e:
        raise HTTPException(401, "bad_token") from e
    for ev in events:
        key = f"{provider.name}:{ev.kind}:{ev.provider_message_id or ''}:{hashlib.sha256(body).hexdigest()[:16]}"
        row = await _claim(f"messaging:{provider.name}", ev.kind, key, ev.raw or json.loads(body or b"{}"))
        if row is None:
            continue
        async with SessionLocal() as db:
            await notify.apply_event(db, ev)
            await notify.commit_and_dispatch(db)
        await _done(row.id)
    return {"ok": True}


@router.post("/shipping/{provider_name}")
async def shipping_webhook(provider_name: str, request: Request):
    provider = get_shipping_provider(provider_name)
    try:
        events = provider.parse_webhook(_headers(request), await request.body())
    except WebhookVerificationError as e:
        raise HTTPException(401, "bad_token") from e
    for ev in events:
        row = await _claim(f"shipping:{provider.name}", ev.status, f"{provider.name}:{ev.event_id}", ev.raw)
        if row is None:
            continue
        async with SessionLocal() as db:
            await shipping_svc.apply_event(db, ev)
            await notify.commit_and_dispatch(db)
        await _done(row.id)
    return {"ok": True}
