"""Catalog CMS: temples, pujas, translations, packages, add-ons, seva plans, FAQs, publishing (PRD §10.1)."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from deps import require_role
from models import (
    AddonItem,
    AddonItemTranslation,
    FaqEntry,
    Package,
    PackageCode,
    PublishStatus,
    Puja,
    PujaKind,
    PujaTranslation,
    SevaPlan,
    StaffRole,
    StaffUser,
    Temple,
    TempleTranslation,
    VenueType,
)
from services import site_config
from services.audit import audit
from services.catalog import puja_detail, temple_summary, tr_for
from services.i18n import LOCALES
from services.publish import validate_puja
from services.revalidate import puja_tags, revalidate

router = APIRouter(prefix="/v1/admin", tags=["admin"])
editor = require_role(StaffRole.catalog_editor)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:150] or "item"


# ------------------------------------------------------------------ temples
class TempleTrIn(BaseModel):
    locale: str
    name: str = Field(min_length=1)
    address: str | None = None
    history_md: str | None = None


class TempleIn(BaseModel):
    slug: str | None = None
    city: str
    state: str
    lat: float | None = None
    lng: float | None = None
    presiding_deity: str
    venue_type: VenueType  # required: venue type shows on every card and page
    photos: list[dict] = Field(default_factory=list)
    translations: list[TempleTrIn] = Field(default_factory=list)


def _temple_admin(t: Temple) -> dict:
    return {**temple_summary(t, "en"), "lat": t.lat, "lng": t.lng, "photos": t.photos,
            "translations": [{"locale": x.locale, "name": x.name, "address": x.address, "history_md": x.history_md}
                             for x in t.translations]}


@router.get("/temples")
async def temples(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(editor)):
    return [_temple_admin(t) for t in (await db.execute(select(Temple).order_by(Temple.id))).scalars()]


@router.post("/temples", status_code=201)
async def create_temple(body: TempleIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(editor)):
    for ph in body.photos:
        if not ph.get("taken_on") and not ph.get("credit"):  # credited stock photos carry no shoot date
            raise HTTPException(400, "photo_requires_date_taken")
    name = next((t.name for t in body.translations if t.locale == "en"), body.translations[0].name
                if body.translations else body.city)
    t = Temple(slug=body.slug or slugify(name), city=body.city, state=body.state, lat=body.lat, lng=body.lng,
               presiding_deity=body.presiding_deity, venue_type=body.venue_type, photos=body.photos)
    t.translations = [TempleTranslation(**x.model_dump()) for x in body.translations if x.locale in LOCALES]
    db.add(t)
    await db.flush()
    await audit(db, staff.id, "temple.create", "temple", t.id, body.model_dump())
    await db.commit()
    return _temple_admin(t)


@router.put("/temples/{temple_id}")
async def update_temple(temple_id: int, body: TempleIn, db: AsyncSession = Depends(get_db),
                        staff: StaffUser = Depends(editor)):
    t = await db.get(Temple, temple_id)
    if t is None:
        raise HTTPException(404, "not_found")
    for ph in body.photos:
        if not ph.get("taken_on") and not ph.get("credit"):  # credited stock photos carry no shoot date
            raise HTTPException(400, "photo_requires_date_taken")
    for f in ("city", "state", "lat", "lng", "presiding_deity", "venue_type", "photos"):
        setattr(t, f, getattr(body, f))
    if body.slug:
        t.slug = body.slug
    await db.execute(delete(TempleTranslation).where(TempleTranslation.temple_id == t.id))
    t.translations = [TempleTranslation(temple_id=t.id, **x.model_dump()) for x in body.translations
                      if x.locale in LOCALES]
    await audit(db, staff.id, "temple.update", "temple", t.id, body.model_dump())
    await db.commit()
    await revalidate([f"temple:{t.id}", "listing", "home"])
    return _temple_admin(t)


# ------------------------------------------------------------------ pujas
class PujaIn(BaseModel):
    temple_id: int
    kind: PujaKind
    slug: str | None = None
    deity_tags: list[str] = Field(default_factory=list)
    dosha_tags: list[str] = Field(default_factory=list)
    benefit_tags: list[str] = Field(default_factory=list)
    tradition: str = ""
    duration_minutes: int = 0
    priests_count: int = 0
    sankalp_language: str = ""
    requires_nakshatra: bool = False
    video_sla_hours: int | None = None
    deliverables: list[str] = Field(default_factory=list)
    prasad_box: list[str] | None = None
    images: list[dict] = Field(default_factory=list)


class PujaTrIn(BaseModel):
    title: str = ""
    subtitle: str | None = None
    occasion_chip: str | None = None
    about_md: str | None = None
    benefits: list[dict] = Field(default_factory=list)
    rituals: list[dict] = Field(default_factory=list)
    faqs: list[dict] = Field(default_factory=list)
    meta_title: str | None = None
    meta_description: str | None = None


class PackageIn(BaseModel):
    code: PackageCode
    max_names: int = Field(ge=1, le=8)
    price_inr_minor: int = Field(ge=0)
    price_usd_minor: int = Field(ge=0)
    active: bool = True


class AddonIn(BaseModel):
    id: int | None = None
    image_key: str | None = None
    price_inr_minor: int = Field(ge=0)
    price_usd_minor: int = Field(ge=0)
    max_qty: int = Field(ge=1, le=50)
    ships_home: bool = False
    active: bool = True
    translations: dict[str, dict] = Field(default_factory=dict)  # locale -> {name, description}


class SevaPlanIn(BaseModel):
    rrule: str
    occurrences: int = Field(ge=1, le=52)
    autopay_allowed: bool = True


async def _fresh(db: AsyncSession, puja_id: int) -> Puja:
    return (await db.execute(select(Puja).where(Puja.id == puja_id)
                             .execution_options(populate_existing=True))).scalar_one()


async def _puja_admin(db: AsyncSession, p: Puja) -> dict:
    p = await _fresh(db, p.id)
    addons = (await db.execute(select(AddonItem).where(AddonItem.puja_id == p.id).order_by(AddonItem.id))).scalars()
    plan = (await db.execute(select(SevaPlan).where(SevaPlan.puja_id == p.id))).scalar_one_or_none()
    return {
        "id": p.id, "temple_id": p.temple_id, "kind": p.kind.value, "slug": p.slug, "status": p.status.value,
        "deity_tags": p.deity_tags, "dosha_tags": p.dosha_tags, "benefit_tags": p.benefit_tags,
        "tradition": p.tradition, "duration_minutes": p.duration_minutes, "priests_count": p.priests_count,
        "sankalp_language": p.sankalp_language, "requires_nakshatra": p.requires_nakshatra,
        "video_sla_hours": p.video_sla_hours, "deliverables": p.deliverables, "prasad_box": p.prasad_box,
        "images": p.images,
        "translations": {t.locale: {"title": t.title, "subtitle": t.subtitle, "occasion_chip": t.occasion_chip,
                                    "about_md": t.about_md, "benefits": t.benefits, "rituals": t.rituals,
                                    "faqs": t.faqs, "meta_title": t.meta_title,
                                    "meta_description": t.meta_description, "published": t.published}
                         for t in p.translations},
        "packages": [{"id": k.id, "code": k.code.value, "max_names": k.max_names,
                      "price_inr_minor": k.price_inr_minor, "price_usd_minor": k.price_usd_minor, "active": k.active}
                     for k in p.packages],
        "addons": [{"id": a.id, "image_key": a.image_key, "price_inr_minor": a.price_inr_minor,
                    "price_usd_minor": a.price_usd_minor, "max_qty": a.max_qty, "ships_home": a.ships_home,
                    "active": a.active,
                    "translations": {t.locale: {"name": t.name, "description": t.description} for t in a.translations}}
                   for a in addons],
        "seva_plan": {"rrule": plan.rrule, "occurrences": plan.occurrences,
                      "autopay_allowed": plan.autopay_allowed} if plan else None,
    }


@router.get("/pujas")
async def pujas(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(require_role(
        StaffRole.catalog_editor, StaffRole.ops_coordinator, StaffRole.support_agent))):
    out = []
    for p in (await db.execute(select(Puja).order_by(Puja.id.desc()))).scalars():
        en = tr_for(p.translations, "en") or (p.translations[0] if p.translations else None)
        out.append({"id": p.id, "title": en.title if en else p.slug, "kind": p.kind.value, "status": p.status.value,
                    "temple": temple_summary(p.temple, "en")["name"], "slug": p.slug,
                    "locales": {t.locale: t.published for t in p.translations}})
    return out


@router.post("/pujas", status_code=201)
async def create_puja(body: PujaIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(editor)):
    p = Puja(**body.model_dump(exclude={"slug"}), slug=body.slug or "puja", status=PublishStatus.draft)
    db.add(p)
    await db.flush()
    await audit(db, staff.id, "puja.create", "puja", p.id, body.model_dump())
    await db.commit()
    return await _puja_admin(db, p)


@router.get("/pujas/{puja_id}")
async def get_puja(puja_id: int, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    return await _puja_admin(db, p)


@router.put("/pujas/{puja_id}")
async def update_puja(puja_id: int, body: PujaIn, db: AsyncSession = Depends(get_db),
                      staff: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    for img in body.images:
        if not img.get("key"):
            raise HTTPException(400, "image_key_required")
    for k, v in body.model_dump(exclude={"slug"}).items():
        setattr(p, k, v)
    if body.slug:
        p.slug = slugify(body.slug)
    await audit(db, staff.id, "puja.update", "puja", p.id, body.model_dump())
    await db.commit()
    if p.status == PublishStatus.published:
        await revalidate(puja_tags(p.id))
    return await _puja_admin(db, p)


@router.put("/pujas/{puja_id}/translations/{locale}")
async def upsert_translation(puja_id: int, locale: str, body: PujaTrIn, db: AsyncSession = Depends(get_db),
                             staff: StaffUser = Depends(editor)):
    if locale not in LOCALES:
        raise HTTPException(404, "unknown_locale")
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    tr = tr_for(p.translations, locale)
    if tr is None:
        tr = PujaTranslation(puja_id=p.id, locale=locale, published=False, **body.model_dump())
        p.translations.append(tr)
    else:
        for k, v in body.model_dump().items():
            setattr(tr, k, v)
        if tr.published:
            # Editing a live translation re-runs publish validation before it goes out.
            errors = await validate_puja(db, p, [locale])
            if errors:
                await db.rollback()
                raise HTTPException(422, {"code": "publish_blocked", "errors": errors})
    if locale == "en" and body.title and p.slug in ("puja", ""):
        p.slug = slugify(body.title)
    await audit(db, staff.id, "puja.translation", "puja", p.id, {"locale": locale, **body.model_dump()})
    await db.commit()
    if tr.published:
        await revalidate(puja_tags(p.id))
    return await _puja_admin(db, p)


@router.put("/pujas/{puja_id}/packages")
async def set_packages(puja_id: int, body: list[PackageIn], db: AsyncSession = Depends(get_db),
                       staff: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    existing = {k.code: k for k in p.packages}
    for pk in body:
        row = existing.get(pk.code)
        if row is None:
            db.add(Package(puja_id=p.id, **pk.model_dump()))
        else:
            for k, v in pk.model_dump().items():
                setattr(row, k, v)
    await audit(db, staff.id, "puja.packages", "puja", p.id, [x.model_dump() for x in body])
    await db.commit()
    if p.status == PublishStatus.published:
        await revalidate(puja_tags(p.id))
    return await _puja_admin(db, p)


@router.put("/pujas/{puja_id}/addons")
async def set_addons(puja_id: int, body: list[AddonIn], db: AsyncSession = Depends(get_db),
                     staff: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    for a in body:
        row = await db.get(AddonItem, a.id) if a.id else None
        if row is None:
            row = AddonItem(puja_id=p.id)
            db.add(row)
        for k in ("image_key", "price_inr_minor", "price_usd_minor", "max_qty", "ships_home", "active"):
            setattr(row, k, getattr(a, k))
        await db.flush()
        await db.execute(delete(AddonItemTranslation).where(AddonItemTranslation.addon_item_id == row.id))
        for loc, tr in a.translations.items():
            if loc in LOCALES and tr.get("name"):
                db.add(AddonItemTranslation(addon_item_id=row.id, locale=loc, name=tr["name"],
                                            description=tr.get("description")))
    await audit(db, staff.id, "puja.addons", "puja", p.id, [x.model_dump() for x in body])
    await db.commit()
    return await _puja_admin(db, p)


@router.put("/pujas/{puja_id}/seva-plan")
async def set_seva_plan(puja_id: int, body: SevaPlanIn, db: AsyncSession = Depends(get_db),
                        staff: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None or p.kind != PujaKind.seva:
        raise HTTPException(400, "not_a_seva")
    from dateutil.rrule import rrulestr

    try:
        rrulestr(body.rrule)
    except Exception as e:
        raise HTTPException(400, "bad_rrule") from e
    plan = (await db.execute(select(SevaPlan).where(SevaPlan.puja_id == p.id))).scalar_one_or_none()
    if plan is None:
        db.add(SevaPlan(puja_id=p.id, **body.model_dump()))
    else:
        for k, v in body.model_dump().items():
            setattr(plan, k, v)
    await audit(db, staff.id, "puja.seva_plan", "puja", p.id, body.model_dump())
    await db.commit()
    return await _puja_admin(db, p)


class PublishIn(BaseModel):
    locales: list[str]


@router.post("/pujas/{puja_id}/validate")
async def validate(puja_id: int, body: PublishIn, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    return {"errors": await validate_puja(db, p, [loc for loc in body.locales if loc in LOCALES])}


@router.post("/pujas/{puja_id}/publish")
async def publish(puja_id: int, body: PublishIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    locales = [loc for loc in body.locales if loc in LOCALES]
    if not locales:
        raise HTTPException(400, "no_locales")
    errors = await validate_puja(db, p, locales)
    if errors:
        raise HTTPException(422, {"code": "publish_blocked", "errors": errors})
    p.status = PublishStatus.published
    for t in p.translations:
        if t.locale in locales:
            t.published = True
    await audit(db, staff.id, "puja.publish", "puja", p.id, {"locales": locales})
    await db.commit()
    ok = await revalidate(puja_tags(p.id))
    return {"published": locales, "revalidated": ok}


@router.post("/pujas/{puja_id}/unpublish")
async def unpublish(puja_id: int, body: PublishIn, db: AsyncSession = Depends(get_db),
                    staff: StaffUser = Depends(editor)):
    p = await db.get(Puja, puja_id)
    if p is None:
        raise HTTPException(404, "not_found")
    for t in p.translations:
        if t.locale in body.locales:
            t.published = False
    if not any(t.published for t in p.translations):
        p.status = PublishStatus.draft
    await audit(db, staff.id, "puja.unpublish", "puja", p.id, {"locales": body.locales})
    await db.commit()
    await revalidate(puja_tags(p.id))
    return {"ok": True}


@router.get("/pujas/{puja_id}/preview/{locale}")
async def preview(puja_id: int, locale: str, currency: str = "INR", db: AsyncSession = Depends(get_db),
                  _: StaffUser = Depends(editor)):
    """Same payload as the public detail endpoint, ignoring publish flags — for the CMS side-by-side preview."""
    p = await db.get(Puja, puja_id)
    if p is None or tr_for(p.translations, locale) is None:
        raise HTTPException(404, "not_found")
    for t in p.translations:  # in-memory only: lets the serializer read unpublished copy
        if t.locale == locale:
            t.published = True
    sla = await site_config.get(db, "video_sla_hours_default")
    data = await puja_detail(db, p, locale, currency, sla)
    await db.rollback()
    data.update({"reviews": [], "recommendations": [], "global_faqs": [], "preview": True})
    return data


# ------------------------------------------------------------------ FAQs
class FaqIn(BaseModel):
    question: str = Field(min_length=3)
    answer_md: str = Field(min_length=3)


@router.get("/faqs/{locale}")
async def get_faqs(locale: str, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(editor)):
    rows = (await db.execute(select(FaqEntry).where(FaqEntry.locale == locale).order_by(FaqEntry.position))).scalars()
    return [{"question": f.question, "answer_md": f.answer_md} for f in rows]


@router.put("/faqs/{locale}")
async def put_faqs(locale: str, body: list[FaqIn], db: AsyncSession = Depends(get_db),
                   staff: StaffUser = Depends(editor)):
    if locale not in LOCALES:
        raise HTTPException(404, "unknown_locale")
    from services.publish import PLACEHOLDER

    for f in body:
        if PLACEHOLDER.search(f.question) or PLACEHOLDER.search(f.answer_md):
            raise HTTPException(422, "placeholder_in_faq")
    await db.execute(delete(FaqEntry).where(FaqEntry.locale == locale))
    for i, f in enumerate(body):
        db.add(FaqEntry(locale=locale, position=i, question=f.question, answer_md=f.answer_md))
    await audit(db, staff.id, "faq.update", "faq", locale, [f.model_dump() for f in body])
    await db.commit()
    await revalidate(["home", "faq"])
    return {"ok": True, "count": len(body)}
