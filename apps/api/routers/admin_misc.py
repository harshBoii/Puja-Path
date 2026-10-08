"""Messaging templates/campaigns, reviews, site config, finance, audit log (PRD §10.9-13)."""

import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from deps import require_role
from models import (
    AuditLog,
    Booking,
    Campaign,
    InboundMessage,
    MessageTemplate,
    Payment,
    Puja,
    ReconciliationItem,
    Refund,
    Review,
    ReviewStatus,
    StaffRole,
    StaffUser,
    User,
)
from providers.messaging import get_messaging_provider
from services import notify, site_config
from services.audit import audit
from services.catalog import puja_title
from services.i18n import LOCALES, utcnow
from services.messaging_templates import TEMPLATE_SPECS, render_body, template_name
from services.revalidate import revalidate

router = APIRouter(prefix="/v1/admin", tags=["admin"])
admin_only = require_role()
finance = require_role(StaffRole.finance)


# ------------------------------------------------------------------ messaging
@router.get("/templates")
async def templates(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(require_role(StaffRole.support_agent))):
    rows = (await db.execute(select(MessageTemplate).where(MessageTemplate.provider == settings.messaging_provider)
                             .order_by(MessageTemplate.key, MessageTemplate.locale))).scalars()
    return {"provider": settings.messaging_provider,
            "templates": [{"key": t.key, "locale": t.locale, "category": t.category, "ref": t.provider_template_ref,
                           "status": t.status, "variables": t.variables, "body": t.body} for t in rows]}


@router.post("/templates/sync")
async def sync_templates(db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(admin_only)):
    """Pulls approval status (and Gupshup template IDs) from the provider, matched by name {prefix}_{key}_{locale}."""
    provider = get_messaging_provider()
    remote = await provider.list_templates()
    by_name = {t.name: t for t in remote}
    updated = 0
    for t in (await db.execute(select(MessageTemplate).where(MessageTemplate.provider == provider.name))).scalars():
        r = by_name.get(template_name(t.key, t.locale)) or by_name.get(template_name(t.key))
        if r is None:
            continue
        t.status = r.status
        t.provider_template_ref = r.provider_ref
        updated += 1
    await audit(db, staff.id, "templates.sync", "message_templates", provider.name, {"updated": updated})
    await db.commit()
    return {"updated": updated, "remote": len(remote)}


class TestSendIn(BaseModel):
    template_key: str
    locale: str
    to_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


@router.post("/templates/test-send")
async def test_send(body: TestSendIn, db: AsyncSession = Depends(get_db),
                    staff: StaffUser = Depends(require_role(StaffRole.support_agent))):
    spec = TEMPLATE_SPECS.get(body.template_key)
    if spec is None or body.locale not in LOCALES:
        raise HTTPException(400, "bad_template")
    if not notify.enabled(body.template_key):
        raise HTTPException(400, "template_disabled")
    params = [f"[{v}]" for v in spec["variables"]]
    await notify.queue(db, template_key=body.template_key, to=body.to_e164, locale=body.locale, params=params,
                       occurrence_key=f"test:{utcnow().timestamp()}")
    await audit(db, staff.id, "templates.test_send", "message_templates", body.template_key, body.model_dump())
    await notify.commit_and_dispatch(db)
    return {"preview": render_body(body.template_key, body.locale, params)}


class CampaignIn(BaseModel):
    template_key: str = Field(pattern="^(festival_offer)$")
    locale: str
    interest_tag: str | None = None  # deity/benefit tag the devotee booked before
    festival: str = Field(min_length=2, max_length=60)
    puja_id: int


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(admin_only)):
    if body.locale not in LOCALES:
        raise HTTPException(400, "bad_locale")
    puja = await db.get(Puja, body.puja_id)
    if puja is None:
        raise HTTPException(404, "not_found")
    cap = await site_config.get(db, "campaign_cap_per_week")
    title = await puja_title(db, puja.id, body.locale)
    camp = Campaign(template_key=body.template_key, locale=body.locale, interest_tag=body.interest_tag,
                    params=[body.festival, title], puja_id=puja.id, created_by=staff.id)
    db.add(camp)
    await db.flush()
    users = (await db.execute(select(User).where(User.marketing_opt_in_at.is_not(None), User.deleted_at.is_(None),
                                                 User.locale == body.locale))).scalars().all()
    sent = skipped = 0
    for u in users:
        if body.interest_tag:
            from models import PujaEvent

            hit = (await db.execute(select(Booking.id).join(PujaEvent, Booking.puja_event_id == PujaEvent.id)
                                    .join(Puja, Puja.id == PujaEvent.puja_id)
                                    .where(Booking.user_id == u.id, (Puja.deity_tags.contains([body.interest_tag]))
                                           | (Puja.benefit_tags.contains([body.interest_tag]))).limit(1))).first()
            if not hit:
                continue
        if await notify.marketing_sends_this_week(db, u.id) >= cap:
            skipped += 1
            continue
        mid = await notify.queue(db, template_key=body.template_key, to=u.phone_e164, locale=body.locale,
                                 user_id=u.id, params=camp.params, occurrence_key=f"campaign:{camp.id}:{u.id}",
                                 button_params=[f"{body.locale}/pujas/{puja.id}-{puja.slug}"])
        if mid:
            from sqlalchemy import update

            from models import MessageLog

            await db.execute(update(MessageLog).where(MessageLog.id == mid).values(campaign_id=camp.id))
            sent += 1
    camp.recipients, camp.skipped_cap = sent, skipped
    await audit(db, staff.id, "campaign.create", "campaign", camp.id, body.model_dump())
    await notify.commit_and_dispatch(db)
    return {"id": camp.id, "recipients": sent, "skipped_cap": skipped}


@router.get("/campaigns")
async def campaigns(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(admin_only)):
    rows = (await db.execute(select(Campaign).order_by(Campaign.created_at.desc()).limit(100))).scalars()
    return [{"id": c.id, "template": c.template_key, "locale": c.locale, "interest_tag": c.interest_tag,
             "recipients": c.recipients, "skipped_cap": c.skipped_cap, "at": c.created_at.isoformat()} for c in rows]


@router.get("/inbound")
async def inbound(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(require_role(StaffRole.support_agent))):
    rows = (await db.execute(select(InboundMessage).order_by(InboundMessage.received_at.desc()).limit(200))).scalars()
    return [{"from": m.from_e164, "text": m.text, "button": m.button_payload,
             "booking_id": str(m.matched_booking_id) if m.matched_booking_id else None,
             "at": m.received_at.isoformat()} for m in rows]


# ------------------------------------------------------------------ reviews
@router.get("/reviews")
async def reviews(status: str = "pending", db: AsyncSession = Depends(get_db),
                  _: StaffUser = Depends(require_role(StaffRole.support_agent, StaffRole.catalog_editor))):
    rows = (await db.execute(select(Review, Booking).join(Booking, Review.booking_id == Booking.id)
                             .where(Review.status == status).order_by(Review.created_at.desc()).limit(200))).all()
    return [{"id": str(r.id), "rating": r.rating, "text": r.text, "locale": r.locale, "status": r.status.value,
             "code": b.code, "title": await puja_title(db, b.event.puja_id, "en"), "at": r.created_at.isoformat()}
            for r, b in rows]


class ModerateIn(BaseModel):
    status: ReviewStatus


@router.post("/reviews/{review_id}")
async def moderate(review_id: str, body: ModerateIn, db: AsyncSession = Depends(get_db),
                   staff: StaffUser = Depends(require_role(StaffRole.support_agent, StaffRole.catalog_editor))):
    import uuid

    r = await db.get(Review, uuid.UUID(review_id))
    if r is None:
        raise HTTPException(404, "not_found")
    r.status = body.status
    await audit(db, staff.id, "review.moderate", "review", r.id, {"status": body.status})
    await db.commit()
    await revalidate(["home", "reviews"])
    return {"ok": True}


# ------------------------------------------------------------------ site config
@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(admin_only)):
    return await site_config.get_all(db)


class ConfigIn(BaseModel):
    value: dict | list | str | int | float | bool | None


@router.put("/config/{key}")
async def put_config(key: str, body: ConfigIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(admin_only)):
    if key not in site_config.DEFAULTS:
        raise HTTPException(404, "unknown_key")
    if key in ("trust_bar_thresholds",) and not isinstance(body.value, dict):
        raise HTTPException(400, "bad_value")
    before = await site_config.get(db, key)
    await site_config.set_value(db, key, body.value)
    await audit(db, staff.id, "config.update", "site_config", key, {"before": before, "after": body.value})
    await db.commit()
    await revalidate(["config", "home", "listing"])
    return {"key": key, "value": body.value}


# ------------------------------------------------------------------ finance
@router.get("/finance/payments")
async def payments(days: int = 30, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(finance)):
    rows = (await db.execute(select(Payment).where(Payment.created_at > utcnow() - timedelta(days=days))
                             .order_by(Payment.created_at.desc()).limit(1000))).scalars()
    return [{"id": str(p.id), "booking_id": str(p.booking_id) if p.booking_id else None,
             "subscription_id": str(p.subscription_id) if p.subscription_id else None, "provider": p.provider,
             "order_id": p.provider_order_id, "payment_id": p.provider_payment_id, "amount_minor": p.amount_minor,
             "currency": p.currency, "status": p.status, "at": p.created_at.isoformat(),
             "settled": p.settled_at is not None} for p in rows]


@router.get("/finance/refunds")
async def refunds(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(finance)):
    rows = (await db.execute(select(Refund).order_by(Refund.created_at.desc()).limit(1000))).scalars()
    return [{"id": str(r.id), "booking_id": str(r.booking_id) if r.booking_id else None, "amount_minor": r.amount_minor,
             "reason": r.reason, "status": r.status, "provider_refund_id": r.provider_refund_id,
             "at": r.created_at.isoformat()} for r in rows]


@router.get("/finance/mismatches")
async def mismatches(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(finance)):
    rows = (await db.execute(select(ReconciliationItem).where(ReconciliationItem.resolved.is_(False))
                             .order_by(ReconciliationItem.run_date.desc()))).scalars()
    return [{"id": r.id, "date": r.run_date.isoformat(), "provider": r.provider, "kind": r.kind,
             "provider_payment_id": r.provider_payment_id, "detail": r.detail} for r in rows]


@router.post("/finance/mismatches/{item_id}/resolve")
async def resolve(item_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(finance)):
    r = await db.get(ReconciliationItem, item_id)
    if r is None:
        raise HTTPException(404, "not_found")
    r.resolved = True
    await audit(db, staff.id, "finance.resolve", "reconciliation_item", item_id)
    await db.commit()
    return {"ok": True}


@router.get("/finance/export.csv")
async def export(days: int = 30, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(finance)):
    rows = (await db.execute(select(Payment, Booking).outerjoin(Booking, Payment.booking_id == Booking.id)
                             .where(Payment.created_at > utcnow() - timedelta(days=days))
                             .order_by(Payment.created_at))).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["created_at", "booking_code", "provider", "order_id", "payment_id", "amount", "currency", "status"])
    for p, b in rows:
        w.writerow([p.created_at.isoformat(), b.code if b else "", p.provider, p.provider_order_id or "",
                    p.provider_payment_id or "", f"{p.amount_minor / 100:.2f}", p.currency, p.status])
    await audit(db, staff.id, "finance.export", "payments", f"{days}d")
    await db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=payments.csv"})


# ------------------------------------------------------------------ audit
@router.get("/audit")
async def audit_log(entity: str | None = None, entity_id: str | None = None, limit: int = 200,
                    db: AsyncSession = Depends(get_db), _: StaffUser = Depends(admin_only)):
    stmt = select(AuditLog, StaffUser).outerjoin(StaffUser, AuditLog.actor_staff_id == StaffUser.id)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = (await db.execute(stmt.order_by(AuditLog.at.desc()).limit(min(limit, 1000)))).all()
    return [{"id": a.id, "actor": s.name if s else "system", "action": a.action, "entity": a.entity,
             "entity_id": a.entity_id, "diff": a.diff, "at": a.at.isoformat()} for a, s in rows]

