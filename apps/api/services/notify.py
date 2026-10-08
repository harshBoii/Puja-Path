"""Outbound WhatsApp: queue -> dispatch -> send, with idempotency, quiet hours, retries (PRD §7 sending rules).

`queue()` inserts a message_log row. The unique key (booking, template, occurrence) makes a second queue
of the same message a no-op, and `send_one()` only sends rows still in `queued`, so retried jobs never double-send.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import SessionLocal
from logging_setup import log
from models import Booking, InboundMessage, MessageLog, MessageStatus, MessageTemplate, User
from providers.errors import ProviderError, RetryableProviderError
from providers.messaging import get_messaging_provider
from providers.messaging.base import INVALID_NUMBER_CODES, MessagingEvent, TemplateRef
from services import site_config
from services.i18n import in_quiet_hours, tz_for_phone, utcnow
from services.messaging_templates import OPT_IN_REQUIRED, TEMPLATE_SPECS, template_name

logger = logging.getLogger("notify")
MAX_ATTEMPTS = 4  # first try + 3 retries
PENDING_KEY = "pending_message_ids"


def enabled(template_key: str) -> bool:
    allowed = {k.strip() for k in settings.messaging_templates.split(",") if k.strip()}
    return not allowed or template_key in allowed


async def queue(
    db: AsyncSession,
    *,
    template_key: str,
    to: str,
    locale: str,
    params: list,
    booking: Booking | None = None,
    user_id: uuid.UUID | None = None,
    occurrence_key: str = "",
    button_params: list | None = None,
    header_media_url: str | None = None,
    scheduled_for: datetime | None = None,
) -> uuid.UUID | None:
    if template_key not in TEMPLATE_SPECS:
        raise ValueError(f"unknown template {template_key}")
    if not enabled(template_key):
        return None  # switched off in MESSAGING_TEMPLATES: no row, no send
    values = dict(
        id=uuid.uuid4(),
        booking_id=booking.id if booking else None,
        user_id=user_id or (booking.user_id if booking else None),
        template_key=template_key,
        occurrence_key=occurrence_key,
        to_e164=to,
        provider=settings.messaging_provider,
        status=MessageStatus.queued,
        locale=locale,
        params=[str(p) for p in params],
        button_params=[str(b) for b in button_params] if button_params else None,
        header_media_url=header_media_url,
        scheduled_for=scheduled_for or utcnow(),
    )
    stmt = insert(MessageLog).values(**values).on_conflict_do_nothing(
        constraint="uq_message_log_booking_tpl_occ"
    ).returning(MessageLog.id)
    new_id = (await db.execute(stmt)).scalar_one_or_none()
    if new_id and (scheduled_for is None or scheduled_for <= utcnow()):
        db.info.setdefault(PENDING_KEY, []).append(str(new_id))
    return new_id


async def commit_and_dispatch(db: AsyncSession) -> None:
    """Commit, then hand freshly queued messages to the worker (the 15 s dispatcher is the safety net)."""
    ids = db.info.pop(PENDING_KEY, [])
    await db.commit()
    if ids:
        from services.jobs import enqueue

        for mid in ids:
            await enqueue("send_message", mid, _job_id=f"msg:{mid}:0")


async def cancel_queued(db: AsyncSession, booking_id: uuid.UUID, template_keys: list[str]) -> None:
    await db.execute(
        update(MessageLog)
        .where(MessageLog.booking_id == booking_id, MessageLog.template_key.in_(template_keys),
               MessageLog.status == MessageStatus.queued)
        .values(status=MessageStatus.failed, error_code="superseded")
    )


async def due_message_ids(db: AsyncSession, limit: int = 200) -> list[str]:
    rows = await db.execute(
        select(MessageLog.id).where(MessageLog.status == MessageStatus.queued,
                                    MessageLog.scheduled_for <= utcnow()).limit(limit)
    )
    return [str(r) for r in rows.scalars()]


async def _template_ref(db: AsyncSession, key: str, locale: str, provider: str) -> TemplateRef:
    row = await db.get(MessageTemplate, (key, locale, provider))
    if row is None or (row.status != "approved" and locale != "en"):
        # Languages can go live one at a time: until this one's template is approved, send the English one.
        en = await db.get(MessageTemplate, (key, "en", provider))
        if en is not None and (row is None or en.status == "approved"):
            row = en
    variables = TEMPLATE_SPECS[key]["variables"]
    if row is None:
        return TemplateRef(key, locale, template_name(key, locale), variables)
    return TemplateRef(key, row.locale, row.provider_template_ref, variables)


async def send_one(message_id: str) -> str:
    """Sends one queued message. Returns a short outcome string (for logs/tests)."""
    async with SessionLocal() as db:
        msg = (await db.execute(
            select(MessageLog).where(MessageLog.id == uuid.UUID(message_id)).with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if msg is None:
            return "locked_or_missing"
        if msg.status != MessageStatus.queued:
            return f"skip:{msg.status.value}"
        now = utcnow()
        if msg.scheduled_for and msg.scheduled_for > now + timedelta(seconds=5):
            return "not_due"

        user = await db.get(User, msg.user_id) if msg.user_id else None
        # Campaign-style marketing needs a current opt-in (STOP removes it).
        if msg.template_key in OPT_IN_REQUIRED and not (user and user.marketing_opt_in_at):
            msg.status, msg.error_code = MessageStatus.failed, "no_marketing_consent"
            await db.commit()
            return "no_consent"

        if msg.template_key != "otp_login":
            quiet = await site_config.get(db, "quiet_hours")
            resume_at = in_quiet_hours(now, tz_for_phone(msg.to_e164, user.timezone if user else None), quiet)
            if resume_at:
                msg.scheduled_for = resume_at
                await db.commit()
                log(logger, "message held for quiet hours", message_id=message_id, booking_id=str(msg.booking_id),
                    resume_at=resume_at.isoformat())
                return "held"

        provider = get_messaging_provider(msg.provider)
        tpl = await _template_ref(db, msg.template_key, msg.locale, msg.provider)
        msg.attempts += 1
        try:
            result = await provider.send_template(
                msg.to_e164, tpl, msg.params, header_media_url=msg.header_media_url,
                button_params=msg.button_params, idempotency_key=str(msg.id),
            )
        except RetryableProviderError as e:
            if msg.attempts >= MAX_ATTEMPTS:
                msg.status, msg.error_code = MessageStatus.failed, (e.code or "timeout")[:60]
            else:
                msg.scheduled_for = now + timedelta(seconds=30 * 2 ** (msg.attempts - 1))
            await db.commit()
            log(logger, "message send retryable error", message_id=message_id, booking_id=str(msg.booking_id),
                attempts=msg.attempts, error=str(e))
            return "retry" if msg.status == MessageStatus.queued else "failed"
        except ProviderError as e:
            msg.status, msg.error_code = MessageStatus.failed, (e.code or "provider_error")[:60]
            await db.commit()
            return "failed"

        if result.accepted:
            msg.status = MessageStatus.sent
            msg.provider_message_id = result.provider_message_id
            msg.sent_at = now
        else:
            msg.status, msg.error_code = MessageStatus.failed, (result.error or "rejected")[:60]
            if result.error in INVALID_NUMBER_CODES and msg.booking_id:
                await _flag_call_queue(db, msg.booking_id)
        log(logger, "message sent" if result.accepted else "message rejected", message_id=message_id,
            booking_id=str(msg.booking_id), template=msg.template_key, provider=msg.provider,
            provider_message_id=result.provider_message_id, error=result.error)

        if result.accepted and msg.template_key == "proof_video" and msg.booking_id:
            from services import bookings as booking_svc

            booking = await db.get(Booking, msg.booking_id)
            if booking:
                await booking_svc.on_proof_sent(db, booking)
        await commit_and_dispatch(db)
        return "sent" if result.accepted else "rejected"


async def _flag_call_queue(db: AsyncSession, booking_id: uuid.UUID) -> None:
    await db.execute(update(Booking).where(Booking.id == booking_id).values(needs_call_reason="whatsapp_invalid_number"))


_STATUS_ORDER = {MessageStatus.queued: 0, MessageStatus.sent: 1, MessageStatus.delivered: 2, MessageStatus.read: 3}


async def apply_event(db: AsyncSession, ev: MessagingEvent) -> None:
    """Applies a normalised provider webhook event."""
    if ev.kind in ("sent", "delivered", "read", "failed"):
        if not ev.provider_message_id:
            return
        msg = (await db.execute(
            select(MessageLog).where(MessageLog.provider_message_id == ev.provider_message_id)
        )).scalar_one_or_none()
        if msg is None:
            return
        new = MessageStatus(ev.kind)
        if new == MessageStatus.failed:
            msg.status, msg.error_code = new, (ev.error_code or "failed")[:60]
            if (ev.error_code or "") in INVALID_NUMBER_CODES and msg.booking_id:
                await _flag_call_queue(db, msg.booking_id)
        elif _STATUS_ORDER.get(new, 0) > _STATUS_ORDER.get(msg.status, 0):  # never move backwards
            msg.status = new
            if new == MessageStatus.delivered:
                msg.delivered_at = utcnow()
            if new == MessageStatus.read:
                msg.read_at = utcnow()
                msg.delivered_at = msg.delivered_at or utcnow()
        log(logger, "message status", booking_id=str(msg.booking_id), template=msg.template_key, status=ev.kind)
        return

    # inbound: log against the devotee's latest booking
    phone = ev.from_e164 or ""
    latest = (await db.execute(
        select(Booking).where(Booking.whatsapp_e164 == phone, Booking.status != "draft")
        .order_by(Booking.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    db.add(InboundMessage(from_e164=phone, text=ev.text, button_payload=ev.button_payload,
                          matched_booking_id=latest.id if latest else None))
    log(logger, "inbound message", booking_id=str(latest.id) if latest else None, kind=ev.kind)

    text = (ev.text or ev.button_payload or "").strip()
    if text.upper() == "STOP":
        await db.execute(update(User).where(User.phone_e164 == phone).values(marketing_opt_in_at=None))
        return
    if latest is None:
        return
    from services import bookings as booking_svc
    from services import reviews as review_svc

    payload = (ev.button_payload or ev.text or "").strip().lower()
    if latest.status.value == "rescheduled" and payload in ("accept", "refund"):
        await booking_svc.answer_reschedule(db, latest, accept=(payload == "accept"))
    elif payload in {"1", "2", "3", "4", "5"}:
        await review_svc.record_rating(db, latest, int(payload))
    elif ev.kind == "inbound_text" and ev.text:
        await review_svc.maybe_attach_text(db, latest, ev.text)


async def marketing_sends_this_week(db: AsyncSession, user_id: uuid.UUID) -> int:
    since = utcnow() - timedelta(days=7)
    rows = await db.execute(
        select(MessageLog.id).where(
            MessageLog.user_id == user_id,
            MessageLog.campaign_id.is_not(None),
            MessageLog.created_at >= since,
            or_(MessageLog.status != MessageStatus.failed, and_(MessageLog.error_code.is_(None))),
        )
    )
    return len(rows.all())
