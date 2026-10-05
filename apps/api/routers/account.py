"""Devotee account: profile, family, bookings, invoices, subscriptions, wishlist, deletion (PRD §5.8)."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from deps import require_user
from models import (
    Booking,
    BookingStatus,
    FamilyMember,
    ProofClip,
    QcStatus,
    Subscription,
    User,
    WishlistItem,
)
from providers.media.storage import public_url
from providers.media.video import playback
from routers.auth import user_dict
from services import bookings as booking_svc
from services import notify, seva, site_config
from services.catalog import image, package_label, puja_title, temple_name
from services.i18n import LOCALES, fmt_dt_ist, fmt_money, utcnow

router = APIRouter(prefix="/v1/account", tags=["account"])
S = BookingStatus


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    locale: str | None = None
    marketing_opt_in: bool | None = None


@router.get("")
async def profile(user: User = Depends(require_user)):
    return {"user": user_dict(user)}


@router.put("")
async def update_profile(body: ProfileIn, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip() or None
    if body.email is not None:
        user.email = str(body.email)
    if body.locale in LOCALES:
        user.locale = body.locale
    if body.marketing_opt_in is not None:
        user.marketing_opt_in_at = utcnow() if body.marketing_opt_in else None
    db.add(user)
    await db.commit()
    return {"user": user_dict(user)}


class FamilyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str | None = Field(default=None, max_length=60)
    gotra: str | None = Field(default=None, max_length=80)
    nakshatra: str | None = Field(default=None, max_length=40)


def _fm(m: FamilyMember) -> dict:
    return {"id": str(m.id), "name": m.name, "relation": m.relation, "gotra": m.gotra, "nakshatra": m.nakshatra}


@router.get("/family")
async def family(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FamilyMember).where(FamilyMember.user_id == user.id)
                             .order_by(FamilyMember.name))).scalars()
    return [_fm(m) for m in rows]


@router.post("/family", status_code=201)
async def add_family(body: FamilyIn, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    m = FamilyMember(user_id=user.id, **body.model_dump())
    db.add(m)
    await db.commit()
    return _fm(m)


@router.put("/family/{member_id}")
async def edit_family(member_id: uuid.UUID, body: FamilyIn, user: User = Depends(require_user),
                      db: AsyncSession = Depends(get_db)):
    m = await db.get(FamilyMember, member_id)
    if m is None or m.user_id != user.id:
        raise HTTPException(404, "not_found")
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    await db.commit()
    return _fm(m)


@router.delete("/family/{member_id}")
async def delete_family(member_id: uuid.UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(FamilyMember).where(FamilyMember.id == member_id, FamilyMember.user_id == user.id))
    await db.commit()
    return {"ok": True}


async def _summary(db: AsyncSession, b: Booking, locale: str) -> dict:
    ev = b.event
    puja = ev.puja
    return {
        "id": str(b.id), "code": b.code, "status": b.status.value, "currency": b.currency,
        "total_minor": b.total_minor, "locale": b.locale, "puja_id": puja.id, "slug": puja.slug,
        "kind": puja.kind.value, "title": await puja_title(db, puja.id, locale),
        "temple": await temple_name(db, puja.temple_id, locale), "starts_at": ev.starts_at.isoformat(),
        "image": image(puja.images[0], locale) if puja.images else None,
        "subscription_id": str(b.subscription_id) if b.subscription_id else None,
    }


@router.get("/bookings")
async def my_bookings(locale: str = "en", user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Booking).where(Booking.user_id == user.id, Booking.status != S.draft)
                             .order_by(Booking.created_at.desc()).limit(200))).scalars().all()
    return [await _summary(db, b, locale) for b in rows]


def _timeline(b: Booking, shipment) -> list[dict]:
    order = [S.confirmed, S.locked, S.performed, S.proof_ready, S.proof_sent, S.completed]
    reached = order.index(b.status) if b.status in order else -1
    steps = [
        {"key": "paid", "done": b.confirmed_at is not None, "at": b.confirmed_at},
        {"key": "scheduled", "done": reached >= 1 or b.confirmed_at is not None, "at": b.event.starts_at},
        {"key": "performed", "done": reached >= 2, "at": b.performed_at},
        {"key": "video_sent", "done": reached >= 4, "at": b.proof_sent_at},
    ]
    if shipment is not None:
        ship_order = ["pending", "packed", "shipped", "out_for_delivery", "delivered"]
        st = shipment.status.value
        idx = ship_order.index(st) if st in ship_order else -1
        steps.append({"key": "shipped", "done": idx >= 2, "at": None})
        steps.append({"key": "delivered", "done": idx >= 4, "at": None})
    return [{**s, "at": s["at"].isoformat() if s["at"] else None} for s in steps]


@router.get("/bookings/{booking_id}")
async def booking_detail(booking_id: uuid.UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    b = await db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "not_found")
    locale = b.locale
    shipment = await booking_svc.get_shipment(db, b.id)
    clip = (await db.execute(select(ProofClip).where(ProofClip.booking_id == b.id,
                                                     ProofClip.qc_status == QcStatus.approved))).scalar_one_or_none()
    ev = b.event
    proof_visible = b.status in (S.proof_ready, S.proof_sent, S.completed)
    return {
        **await _summary(db, b, locale),
        "package": package_label(b.package.code.value, locale),
        "names": [{"name": n.name, "relation": n.relation, "gotra": n.gotra, "gotra_unknown": n.gotra_unknown,
                   "nakshatra": n.nakshatra} for n in b.names],
        "wish": b.wish, "booking_cutoff_at": ev.booking_cutoff_at.isoformat(),
        "video_sla_hours": ev.video_sla_hours,
        "can_cancel": booking_svc.can_devotee_cancel(b),
        "timeline": _timeline(b, shipment),
        "proof": {"clip": {"url": public_url(clip.r2_key), "poster": public_url(clip.thumb_key)} if clip else None,
                  "full_video": playback(ev.full_video_stream_id),
                  "photos": [{"url": public_url(p.get("key")), "alt": (p.get("alt") or {}).get(locale, "")}
                             for p in (ev.photos or [])],
                  "share_path": booking_svc.proof_path(b)} if proof_visible else None,
        "shipment": {"status": shipment.status.value, "courier": shipment.courier, "awb": shipment.awb,
                     "tracking_url": shipment.tracking_url} if shipment else None,
        "pricing": {"package_minor": b.subtotal_minor, "addons_minor": b.addons_minor,
                    "shipping_minor": b.shipping_minor, "dakshina_minor": b.dakshina_minor, "tax_minor": b.tax_minor,
                    "total_minor": b.total_minor},
        "has_invoice": b.confirmed_at is not None,
    }


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: uuid.UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    b = await db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "not_found")
    if not booking_svc.can_devotee_cancel(b):
        raise HTTPException(409, "cancel_window_closed")
    await booking_svc.cancel(db, b, reason="devotee_cancelled")
    await notify.commit_and_dispatch(db)
    return {"status": b.status.value}


async def invoice_file(db: AsyncSession, b: Booking):
    from services.pdf import invoice_pdf

    locale = "en"  # invoices are issued in English for accounting; names keep their original script
    cur = b.currency
    lines = [(f"{await puja_title(db, b.event.puja_id, locale)} — {package_label(b.package.code.value, locale)}",
              fmt_money(b.subtotal_minor, cur, locale))]
    for a in b.addons:
        from services.catalog import tr_fallback

        tr = tr_fallback(a.item.translations, locale)
        lines.append((f"{tr.name if tr else 'Offering'} × {a.qty}", fmt_money(a.qty * a.unit_price_minor, cur, locale)))
    if b.shipping_minor:
        lines.append(("Prasad delivery", fmt_money(b.shipping_minor, cur, locale)))
    if b.dakshina_minor:
        lines.append(("Dakshina", fmt_money(b.dakshina_minor, cur, locale)))
    tax_rules = await site_config.get(db, "tax_rules")
    for rule in tax_rules or []:
        amt = (b.subtotal_minor + b.addons_minor) * int(rule.get("rate_bps", 0)) // 10000
        lines.append((rule.get("label", "Tax"), fmt_money(amt, cur, locale)))
    return invoice_pdf(
        booking={"code": b.code, "puja": await puja_title(db, b.event.puja_id, locale),
                 "temple": await temple_name(db, b.event.puja.temple_id, locale),
                 "datetime": fmt_dt_ist(b.event.starts_at, locale),
                 "name": b.names[0].name if b.names else "", "phone": b.whatsapp_e164 or ""},
        lines=lines, total=fmt_money(b.total_minor, cur, locale), invoice_no=f"INV-{b.code}",
        issued=(b.confirmed_at or utcnow()).date().isoformat(),
        tax_note=None if tax_rules else "No tax is charged on this booking.",
    )


@router.get("/bookings/{booking_id}/invoice.pdf")
async def invoice(booking_id: uuid.UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    b = await db.get(Booking, booking_id)
    if b is None or b.user_id != user.id or b.confirmed_at is None:
        raise HTTPException(404, "not_found")
    path = await invoice_file(db, b)
    return FileResponse(path, media_type="application/pdf", filename=f"invoice-{b.code}.pdf")


@router.get("/bookings/{booking_id}/calendar.ics")
async def calendar(booking_id: uuid.UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    b = await db.get(Booking, booking_id)
    if b is None or b.user_id != user.id:
        raise HTTPException(404, "not_found")
    ev = b.event
    title = await puja_title(db, ev.puja_id, b.locale)
    temple = await temple_name(db, ev.puja.temple_id, b.locale)

    def ics_dt(d):
        return d.strftime("%Y%m%dT%H%M%SZ")

    end = ev.starts_at + timedelta(minutes=ev.puja.duration_minutes)
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//puja-path//booking//EN", "BEGIN:VEVENT",
        f"UID:{b.id}@puja-path", f"DTSTAMP:{ics_dt(utcnow())}", f"DTSTART:{ics_dt(ev.starts_at)}",
        f"DTEND:{ics_dt(end)}", f"SUMMARY:{title}", f"LOCATION:{temple}", f"DESCRIPTION:Booking {b.code}",
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    return Response(body, media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="puja-{b.code}.ics"'})


@router.get("/subscriptions")
async def subscriptions(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    return await seva.subscriptions_for_user(db, user.id)


@router.post("/subscriptions/{sub_id}/cancel")
async def cancel_subscription(sub_id: uuid.UUID, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    sub = await db.get(Subscription, sub_id)
    if sub is None or sub.user_id != user.id:
        raise HTTPException(404, "not_found")
    result = await seva.cancel_subscription(db, sub)
    await notify.commit_and_dispatch(db)
    return {"status": sub.status.value, **result}


@router.get("/wishlist")
async def wishlist(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(WishlistItem.puja_id).where(WishlistItem.user_id == user.id))).scalars()
    return {"puja_ids": list(rows)}


@router.put("/wishlist/{puja_id}")
async def wish_add(puja_id: int, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy.dialects.postgresql import insert

    await db.execute(insert(WishlistItem).values(user_id=user.id, puja_id=puja_id).on_conflict_do_nothing())
    await db.commit()
    return {"ok": True}


@router.delete("/wishlist/{puja_id}")
async def wish_remove(puja_id: int, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.puja_id == puja_id))
    await db.commit()
    return {"ok": True}


@router.post("/delete-request")
async def delete_request(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    """Removes or anonymises personal data within 30 days (purge job), keeping invoices the law requires."""
    if user.deletion_requested_at is None:
        user.deletion_requested_at = utcnow()
        await db.commit()
    return {"requested_at": user.deletion_requested_at.isoformat(),
            "complete_by": (user.deletion_requested_at + timedelta(days=30)).date().isoformat()}
