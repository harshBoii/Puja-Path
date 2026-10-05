"""Checkout: draft -> sankalp details -> add-ons -> review & pay (PRD §5.7, §8)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from deps import optional_user, require_user
from models import (
    AddonItem,
    Booking,
    BookingAddon,
    BookingName,
    BookingStatus,
    FamilyMember,
    Package,
    Puja,
    PujaEvent,
    Shipment,
    ShipmentStatus,
    User,
)
from providers.shipping import get_shipping_provider
from services import bookings as booking_svc
from services import site_config
from services.catalog import addon_dict, event_dict, image, package_label, puja_title, temple_name
from services.i18n import LOCALES, utcnow

router = APIRouter(prefix="/v1", tags=["checkout"])
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula",
    "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]


def _err(code: str, status: int = 400):
    raise HTTPException(status, code)


class DraftIn(BaseModel):
    puja_id: int
    event_id: int | None = None
    package_id: int
    locale: str = "en"
    currency: str = Field(default="INR", pattern="^(INR|USD)$")


@router.post("/drafts", status_code=201)
async def create_draft(body: DraftIn, db: AsyncSession = Depends(get_db), user: User | None = Depends(optional_user)):
    from services.catalog import next_event

    ev = await db.get(PujaEvent, body.event_id) if body.event_id else await next_event(db, body.puja_id)
    pkg = await db.get(Package, body.package_id)
    if ev is None or pkg is None or ev.puja_id != body.puja_id:
        _err("not_bookable", 404)
    try:
        b = await booking_svc.create_draft(db, event=ev, package=pkg, locale=body.locale if body.locale in LOCALES
                                           else "en", currency=body.currency, user=user)
    except booking_svc.BookingError as e:
        _err(e.code, 409)
    await db.commit()
    return {"id": str(b.id)}


async def _load(db: AsyncSession, draft_id: uuid.UUID, user: User | None) -> Booking:
    b = await db.get(Booking, draft_id)
    if b is None:
        _err("not_found", 404)
    if b.user_id and (user is None or user.id != b.user_id):
        _err("login_required", 401)
    return b


async def draft_view(db: AsyncSession, b: Booking) -> dict:
    ev = b.event
    puja: Puja = ev.puja
    cfg = await site_config.get_all(db)
    seva_plan = await booking_svc._seva_plan(db, puja.id)
    pricing = await booking_svc.reprice(db, b, occurrences=seva_plan.occurrences if seva_plan else 1)
    shipment = await booking_svc.get_shipment(db, b.id)
    addons = [] if seva_plan else (await db.execute(
        select(AddonItem).where(AddonItem.puja_id == puja.id, AddonItem.active.is_(True)).order_by(AddonItem.id)
    )).scalars().all()
    return {
        "id": str(b.id), "code": b.code, "status": b.status.value, "locale": b.locale, "currency": b.currency,
        "puja": {"id": puja.id, "slug": puja.slug, "kind": puja.kind.value,
                 "title": await puja_title(db, puja.id, b.locale),
                 "temple": await temple_name(db, puja.temple_id, b.locale),
                 "image": image(puja.images[0], b.locale) if puja.images else None,
                 "requires_nakshatra": puja.requires_nakshatra, "prasad_box": puja.prasad_box,
                 "sankalp_language": puja.sankalp_language},
        "event": event_dict(ev),
        "package": {"id": b.package.id, "code": b.package.code.value, "max_names": b.package.max_names,
                    "label": package_label(b.package.code.value, b.locale)},
        "packages": [{"id": p.id, "code": p.code.value, "max_names": p.max_names,
                      "label": package_label(p.code.value, b.locale),
                      "price_minor": p.price_usd_minor if b.currency == "USD" else p.price_inr_minor}
                     for p in puja.packages if p.active],
        "names": [{"name": n.name, "relation": n.relation, "gotra": n.gotra, "gotra_unknown": n.gotra_unknown,
                   "nakshatra": n.nakshatra} for n in b.names],
        "whatsapp_e164": b.whatsapp_e164, "wish": b.wish,
        "addons": [{"id": a.addon_item_id, "qty": a.qty} for a in b.addons],
        "available_addons": [addon_dict(a, b.locale, b.currency) for a in addons],
        "prasad": shipment is not None, "address": shipment.address if shipment else None,
        "dakshina_minor": b.dakshina_minor, "dakshina_options": cfg["dakshina_options"].get(b.currency, []),
        "shipping_fee_minor": cfg["shipping_fee"].get(b.currency, 0),
        "consent_whatsapp": b.consent_whatsapp_at is not None, "consent_marketing": b.consent_marketing_at is not None,
        "consent_text_version": cfg["consent_text_version"],
        "gotra_fallback": cfg["gotra_fallback"].get(b.locale) or cfg["gotra_fallback"].get("en"),
        "nakshatras": NAKSHATRAS,
        "pricing": pricing,
        "seva": {"occurrences": seva_plan.occurrences, "autopay_allowed": seva_plan.autopay_allowed
                 and b.currency == "INR", "per_occurrence_minor": pricing["total_minor"],
                 "full_total_minor": pricing["total_minor"] * seva_plan.occurrences} if seva_plan else None,
        "payment_expires_at": b.payment_expires_at.isoformat() if b.payment_expires_at else None,
        "subscription_id": str(b.subscription_id) if b.subscription_id else None,
    }


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: User | None = Depends(optional_user)):
    b = await _load(db, draft_id, user)
    view = await draft_view(db, b)
    await db.rollback()  # reprice in view must not persist on GET
    return view


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str | None = Field(default=None, max_length=60)
    gotra: str | None = Field(default=None, max_length=80)
    gotra_unknown: bool = False
    nakshatra: str | None = Field(default=None, max_length=40)

    @field_validator("name")
    @classmethod
    def strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("required")
        return v


class AddonIn(BaseModel):
    id: int
    qty: int = Field(ge=0, le=50)


class AddressIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=r"^\+?\d{10,15}$")
    line1: str = Field(min_length=3, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    pincode: str = Field(pattern=r"^\d{6}$")
    country: str = "IN"


class DraftUpdate(BaseModel):
    package_id: int | None = None
    names: list[NameIn] | None = None
    whatsapp_e164: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")
    wish: str | None = Field(default=None, max_length=140)
    addons: list[AddonIn] | None = None
    prasad: bool | None = None
    address: AddressIn | None = None
    dakshina_minor: int | None = Field(default=None, ge=0)
    consent_whatsapp: bool | None = None
    consent_marketing: bool | None = None
    save_family: bool = False


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: uuid.UUID, body: DraftUpdate, db: AsyncSession = Depends(get_db),
                       user: User | None = Depends(optional_user)):
    b = await _load(db, draft_id, user)
    if b.status not in (BookingStatus.draft, BookingStatus.pending_payment) or b.subscription_id:
        _err("not_editable", 409)
    if b.status == BookingStatus.pending_payment:
        b.status = BookingStatus.draft  # editing after Pay: the next Pay creates a fresh order at the new price
        b.payment_expires_at = None
    puja = b.event.puja
    seva_plan = await booking_svc._seva_plan(db, puja.id)
    cfg = await site_config.get_all(db)

    if body.package_id is not None and body.package_id != b.package_id:
        pkg = await db.get(Package, body.package_id)
        if pkg is None or pkg.puja_id != puja.id or not pkg.active:
            _err("bad_package")
        b.package_id, b.package = pkg.id, pkg
    if body.names is not None:
        if len(body.names) > b.package.max_names:
            _err("too_many_names")
        for n in body.names:
            if puja.requires_nakshatra and not n.nakshatra:
                _err("nakshatra_required")
            if not n.gotra_unknown and not (n.gotra or "").strip():
                _err("gotra_required")
        await db.execute(delete(BookingName).where(BookingName.booking_id == b.id))
        b.names = [BookingName(booking_id=b.id, position=i, name=n.name, relation=n.relation,
                               gotra=None if n.gotra_unknown else (n.gotra or "").strip(),
                               gotra_unknown=n.gotra_unknown, nakshatra=n.nakshatra)
                   for i, n in enumerate(body.names, start=1)]
        if body.save_family and user:
            existing = {m.name.lower() for m in (await db.execute(
                select(FamilyMember).where(FamilyMember.user_id == user.id))).scalars()}
            for n in body.names:
                if n.name.lower() not in existing:
                    db.add(FamilyMember(user_id=user.id, name=n.name, relation=n.relation,
                                        gotra=None if n.gotra_unknown else n.gotra, nakshatra=n.nakshatra))
    if len(b.names) > b.package.max_names:
        _err("too_many_names")
    if body.whatsapp_e164 is not None:
        b.whatsapp_e164 = body.whatsapp_e164
    if body.wish is not None:
        b.wish = body.wish.strip() or None
    if body.addons is not None:
        if seva_plan:
            _err("addons_not_available")
        await db.execute(delete(BookingAddon).where(BookingAddon.booking_id == b.id))
        new = []
        for a in body.addons:
            if a.qty == 0:
                continue
            item = await db.get(AddonItem, a.id)
            if item is None or item.puja_id != puja.id or not item.active or a.qty > item.max_qty:
                _err("bad_addon")
            new.append(BookingAddon(booking_id=b.id, addon_item_id=item.id, qty=a.qty, unit_price_minor=0,
                                    item=item))
        b.addons = new
    if body.dakshina_minor is not None:
        options = cfg["dakshina_options"].get(b.currency, [])
        if body.dakshina_minor not in (0, *options):
            _err("bad_dakshina")
        b.dakshina_minor = body.dakshina_minor

    needs_address = any(a.item and a.item.ships_home for a in b.addons)
    shipment = await booking_svc.get_shipment(db, b.id)
    want_prasad = body.prasad if body.prasad is not None else (shipment is not None)
    if want_prasad and not (puja.prasad_box or needs_address):
        _err("prasad_not_available")
    if (want_prasad or needs_address) and not seva_plan:
        # A shipment row is what "prasad / courier delivery selected" means; it needs a serviceable India address.
        if body.address is not None:
            addr = body.address.model_dump()
            if addr.get("country", "IN") != "IN":
                _err("prasad_india_only")
            res = await get_shipping_provider().check_serviceability(addr["pincode"])
            if not res.serviceable:
                _err("pincode_not_serviceable")
            if shipment is None:
                db.add(Shipment(booking_id=b.id, address=addr, status=ShipmentStatus.pending, events=[]))
            else:
                shipment.address = addr
        elif shipment is None and body.prasad:
            _err("address_required")
    elif shipment is not None and shipment.status == ShipmentStatus.pending:
        await db.delete(shipment)

    now = utcnow()
    if body.consent_whatsapp is not None:
        b.consent_whatsapp_at = now if body.consent_whatsapp else None
        b.consent_text_version = cfg["consent_text_version"] if body.consent_whatsapp else None
    if body.consent_marketing is not None:
        b.consent_marketing_at = now if body.consent_marketing else None
        if user:
            user.marketing_opt_in_at = now if body.consent_marketing else None
    await db.flush()
    view = await draft_view(db, b)
    await db.commit()
    return view


class PayIn(BaseModel):
    payment_mode: str = Field(default="full", pattern="^(full|autopay)$")
    consent_terms: bool
    expected_total_minor: int  # the total the devotee saw; charged total must equal it (PRD §12 drip pricing)


@router.post("/drafts/{draft_id}/pay")
async def pay(draft_id: uuid.UUID, body: PayIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_user)):
    b = await _load(db, draft_id, user)
    if not body.consent_terms:
        _err("terms_required")
    if not b.consent_whatsapp_at:
        _err("whatsapp_consent_required")
    shipment = await booking_svc.get_shipment(db, b.id)
    if any(a.item and a.item.ships_home for a in b.addons) and shipment is None:
        _err("address_required")
    if b.user_id is None:
        b.user_id = user.id
    if b.consent_marketing_at and not user.marketing_opt_in_at:
        user.marketing_opt_in_at = b.consent_marketing_at
    seva_plan = await booking_svc._seva_plan(db, b.event.puja_id)
    pricing = await booking_svc.reprice(db, b)
    expected = pricing["total_minor"]
    if seva_plan and not b.subscription_id and body.payment_mode == "full":
        expected = pricing["total_minor"] * seva_plan.occurrences
    if body.expected_total_minor != expected:
        _err("price_changed", 409)
    try:
        result = await booking_svc.start_payment(db, b, user, payment_mode=body.payment_mode)
    except booking_svc.BookingError as e:
        await db.rollback()
        _err(e.code, 409)
    await db.commit()
    return {**result, "booking_id": str(b.id), "code": b.code}


@router.get("/bookings/{booking_id}/status")
async def booking_status(booking_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         user: User | None = Depends(optional_user)):
    b = await _load(db, booking_id, user)
    return {"id": str(b.id), "code": b.code, "status": b.status.value, "video_sla_hours": b.event.video_sla_hours,
            "confirmed_at": b.confirmed_at.isoformat() if b.confirmed_at else None}
