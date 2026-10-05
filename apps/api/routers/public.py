"""Public catalog API consumed by the storefront (server-side)."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from deps import currency_param, locale_param
from models import (
    Booking,
    BookingName,
    BookingStatus,
    CallbackRequest,
    EventStatus,
    FaqEntry,
    MediaAsset,
    Package,
    PublishStatus,
    Puja,
    PujaEvent,
    PujaKind,
    PujaTranslation,
    Review,
    ReviewStatus,
    SevaPlan,
    Shipment,
    Temple,
    TempleTranslation,
)
from providers.shipping import get_shipping_provider
from services import site_config
from services.catalog import (
    cards,
    event_dict,
    image,
    load_puja,
    puja_detail,
    temple_summary,
    tr_fallback,
    tr_for,
)
from services.i18n import IST, utcnow
from services.proof import proof_page
from services.trust import trust_bar

router = APIRouter(prefix="/v1", tags=["public"])
PAGE = 12


@router.get("/config")
async def public_config(db: AsyncSession = Depends(get_db)):
    from config import settings

    cfg = await site_config.get_all(db)
    return {"brand": settings.brand, **{k: cfg[k] for k in site_config.PUBLIC_KEYS}}


def _paid_states():
    return [BookingStatus.confirmed, BookingStatus.locked, BookingStatus.performed, BookingStatus.proof_ready,
            BookingStatus.proof_sent, BookingStatus.completed]


async def _list(db: AsyncSession, locale: str, currency: str, *, kinds: list[PujaKind], deity=None, dosha=None,
                benefit=None, temple=None, date=None, q=None, sort="soonest", offset=0, limit=PAGE,
                freq: str | None = None, exclude: int | None = None) -> dict:
    now = utcnow()
    next_ev = (select(PujaEvent.puja_id.label("pid"), func.min(PujaEvent.starts_at).label("next_at"))
               .where(PujaEvent.booking_cutoff_at > now, PujaEvent.status == EventStatus.scheduled)
               .group_by(PujaEvent.puja_id))
    if date in ("this_week", "next_week"):
        today = now.astimezone(IST).date()
        week_start = today - timedelta(days=today.weekday())
        if date == "next_week":
            week_start += timedelta(days=7)
        from datetime import datetime, time

        lo = datetime.combine(week_start, time.min, tzinfo=IST)
        next_ev = next_ev.where(PujaEvent.starts_at >= lo, PujaEvent.starts_at < lo + timedelta(days=7))
    next_ev = next_ev.subquery()
    price = (select(Package.puja_id.label("pid"),
                    func.min(Package.price_usd_minor if currency == "USD" else Package.price_inr_minor).label("p"))
             .where(Package.active.is_(True)).group_by(Package.puja_id).subquery())
    booked = (select(PujaEvent.puja_id.label("pid"), func.count(Booking.id).label("n"))
              .join(Booking, Booking.puja_event_id == PujaEvent.id)
              .where(Booking.status.in_(_paid_states())).group_by(PujaEvent.puja_id).subquery())
    tt = select(TempleTranslation).where(TempleTranslation.locale == locale).subquery()

    stmt = (select(Puja.id, next_ev.c.next_at)
            .join(PujaTranslation, and_(PujaTranslation.puja_id == Puja.id, PujaTranslation.locale == locale,
                                        PujaTranslation.published.is_(True)))
            .join(next_ev, next_ev.c.pid == Puja.id)
            .join(Temple, Temple.id == Puja.temple_id)
            .outerjoin(tt, tt.c.temple_id == Puja.temple_id)
            .outerjoin(price, price.c.pid == Puja.id)
            .outerjoin(booked, booked.c.pid == Puja.id)
            .where(Puja.status == PublishStatus.published, Puja.kind.in_(kinds)))
    if deity:
        stmt = stmt.where(Puja.deity_tags.contains([deity]))
    if dosha:
        stmt = stmt.where(Puja.dosha_tags.contains([dosha]))
    if benefit:
        stmt = stmt.where(Puja.benefit_tags.contains([benefit]))
    if temple:
        stmt = stmt.where(Puja.temple_id == int(temple))
    if exclude:
        stmt = stmt.where(Puja.id != exclude)
    if date == "festival":
        stmt = stmt.where(func.coalesce(PujaTranslation.occasion_chip, "") != "")
    if freq:
        stmt = stmt.join(SevaPlan, SevaPlan.puja_id == Puja.id).where(SevaPlan.rrule.ilike(f"%FREQ={freq.upper()}%"))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            PujaTranslation.title.ilike(like), func.similarity(PujaTranslation.title, q) > 0.3,
            tt.c.name.ilike(like), func.similarity(tt.c.name, q) > 0.3,
            func.array_to_string(Puja.deity_tags, " ").ilike(like), Temple.presiding_deity.ilike(like),
        ))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    order = {"price": [price.c.p.asc().nulls_last(), next_ev.c.next_at],
             "popular": [func.coalesce(booked.c.n, 0).desc(), next_ev.c.next_at]}.get(sort, [next_ev.c.next_at])
    rows = (await db.execute(stmt.order_by(*order, Puja.id).offset(offset).limit(limit))).all()
    items = await cards(db, [pid for pid, _ in rows], locale, currency)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{locale}/pujas")
async def list_pujas(locale: str = Depends(locale_param), currency: str = Depends(currency_param),
                     deity: str | None = None, dosha: str | None = None, benefit: str | None = None,
                     temple: str | None = None, date: str | None = None, q: str | None = None,
                     sort: str = "soonest", offset: int = Query(0, ge=0), limit: int = Query(PAGE, le=48),
                     kind: str | None = None, exclude: int | None = None, db: AsyncSession = Depends(get_db)):
    kinds = [PujaKind(kind)] if kind in ("one_time", "chadhava") else [PujaKind.one_time, PujaKind.chadhava]
    return await _list(db, locale, currency, kinds=kinds, deity=deity, dosha=dosha, benefit=benefit, temple=temple,
                       date=date, q=q, sort=sort, offset=offset, limit=limit, exclude=exclude)


@router.get("/{locale}/sevas")
async def list_sevas(locale: str = Depends(locale_param), currency: str = Depends(currency_param),
                     freq: str | None = Query(None, pattern="^(daily|weekly|monthly)$"),
                     offset: int = Query(0, ge=0), limit: int = Query(PAGE, le=48),
                     db: AsyncSession = Depends(get_db)):
    return await _list(db, locale, currency, kinds=[PujaKind.seva], freq=freq, offset=offset, limit=limit)


@router.get("/{locale}/pujas/{puja_id}")
async def get_puja(puja_id: int, locale: str = Depends(locale_param), currency: str = Depends(currency_param),
                   db: AsyncSession = Depends(get_db)):
    p = await load_puja(db, puja_id)
    if p is None or p.status != PublishStatus.published:
        raise HTTPException(404, "not_found")
    sla_default = await site_config.get(db, "video_sla_hours_default")
    detail = await puja_detail(db, p, locale, currency, sla_default)
    if detail is None:
        raise HTTPException(404, "not_in_locale")
    detail["reviews"] = await _reviews(db, locale, puja_id=p.id, temple_id=p.temple_id, limit=6)
    rec_tags = p.deity_tags[:1] or []
    recs = await _list(db, locale, currency, kinds=[PujaKind.one_time, PujaKind.chadhava, PujaKind.seva],
                       deity=rec_tags[0] if rec_tags else None, limit=4, exclude=p.id)
    if len(recs["items"]) < 4 and p.benefit_tags:
        more = await _list(db, locale, currency, kinds=[PujaKind.one_time, PujaKind.chadhava],
                           benefit=p.benefit_tags[0], limit=4, exclude=p.id)
        seen = {i["id"] for i in recs["items"]}
        recs["items"] += [i for i in more["items"] if i["id"] not in seen][: 4 - len(recs["items"])]
    detail["recommendations"] = recs["items"]
    detail["global_faqs"] = await _faqs(db, locale)
    return detail


async def _faqs(db: AsyncSession, locale: str, limit: int = 8) -> list[dict]:
    rows = (await db.execute(select(FaqEntry).where(FaqEntry.locale == locale).order_by(FaqEntry.position)
                             .limit(limit))).scalars().all()
    return [{"q": f.question, "a": f.answer_md} for f in rows]


async def _reviews(db: AsyncSession, locale: str, *, puja_id: int | None = None, temple_id: int | None = None,
                   limit: int = 6) -> list[dict]:
    stmt = (select(Review, Booking, PujaEvent).join(Booking, Review.booking_id == Booking.id)
            .join(PujaEvent, Booking.puja_event_id == PujaEvent.id).join(Puja, Puja.id == PujaEvent.puja_id)
            .where(Review.status == ReviewStatus.approved, Review.locale == locale))
    if puja_id or temple_id:
        stmt = stmt.where(or_(Puja.id == puja_id, Puja.temple_id == temple_id))
    rows = (await db.execute(stmt.order_by(Review.created_at.desc()).limit(limit))).all()
    out = []
    for r, b, ev in rows:
        first = (await db.execute(select(BookingName.name).where(BookingName.booking_id == b.id)
                                  .order_by(BookingName.position).limit(1))).scalar() or ""
        ship = (await db.execute(select(Shipment.address).where(Shipment.booking_id == b.id))).scalar()
        from services.catalog import puja_title

        out.append({"rating": r.rating, "text": r.text, "first_name": first.split(" ")[0],
                    "city": (ship or {}).get("city"), "puja": await puja_title(db, ev.puja_id, locale),
                    "puja_id": ev.puja_id, "date": ev.starts_at.isoformat()})
    return out


@router.get("/{locale}/home")
async def home(locale: str = Depends(locale_param), currency: str = Depends(currency_param),
               db: AsyncSession = Depends(get_db)):
    hero_ids = (await site_config.get(db, "hero_puja_ids") or [])[:5]
    published = set((await db.execute(
        select(Puja.id).join(PujaTranslation, PujaTranslation.puja_id == Puja.id)
        .where(Puja.id.in_(hero_ids), Puja.status == PublishStatus.published, PujaTranslation.locale == locale,
               PujaTranslation.published.is_(True))
    )).scalars())
    hero = [c for c in await cards(db, [i for i in hero_ids if i in published], locale, currency) if c["event"]]
    upcoming = await _list(db, locale, currency, kinds=[PujaKind.one_time, PujaKind.chadhava], limit=24)
    if not hero:
        hero = upcoming["items"][:5]
    sevas = await _list(db, locale, currency, kinds=[PujaKind.seva], limit=3)
    temples = (await db.execute(select(Temple).order_by(Temple.id))).scalars().all()
    gallery = (await db.execute(
        select(MediaAsset).where(MediaAsset.in_gallery.is_(True), MediaAsset.temple_id.is_not(None),
                                 MediaAsset.taken_on.is_not(None)).order_by(MediaAsset.taken_on.desc()).limit(8)
    )).scalars().all()
    tags = {"deity": set(), "dosha": set(), "benefit": set()}
    for it in upcoming["items"]:
        tags["deity"].update(it["deity_tags"])
        tags["dosha"].update(it["dosha_tags"])
        tags["benefit"].update(it["benefit_tags"])
    return {
        "hero": hero,
        "trust": await trust_bar(db),
        "video_sla_hours": await site_config.get(db, "video_sla_hours_default"),
        "upcoming": upcoming["items"],
        "upcoming_total": upcoming["total"],
        "tags": {k: sorted(v) for k, v in tags.items()},
        "sevas": sevas["items"],
        "temples": [temple_summary(t, locale) for t in temples if tr_for(t.translations, locale)],
        "gallery": [{**image({"key": g.key, "alt": g.alt}, locale), "temple": temple_summary(
            await db.get(Temple, g.temple_id), locale)["name"], "taken_on": g.taken_on.isoformat()} for g in gallery],
        "testimonials": await _reviews(db, locale, limit=6),
        "faqs": await _faqs(db, locale),
    }


@router.get("/{locale}/temples")
async def temples(locale: str = Depends(locale_param), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Temple).order_by(Temple.id))).scalars().all()
    return [temple_summary(t, locale) for t in rows if tr_for(t.translations, locale)]


@router.get("/{locale}/temples/{temple_id}")
async def temple(temple_id: int, locale: str = Depends(locale_param), currency: str = Depends(currency_param),
                 db: AsyncSession = Depends(get_db)):
    t = await db.get(Temple, temple_id)
    if t is None or not tr_for(t.translations, locale):
        raise HTTPException(404, "not_found")
    tr = tr_fallback(t.translations, locale)
    pujas = await _list(db, locale, currency, kinds=[PujaKind.one_time, PujaKind.chadhava, PujaKind.seva],
                        temple=str(temple_id), limit=48)
    return {**temple_summary(t, locale), "history_md": tr.history_md, "address": tr.address, "lat": t.lat,
            "lng": t.lng, "photos": [image(p, locale) for p in t.photos], "pujas": pujas["items"],
            "available_locales": sorted(x.locale for x in t.translations)}


@router.get("/{locale}/faqs")
async def faqs(locale: str = Depends(locale_param), db: AsyncSession = Depends(get_db)):
    return await _faqs(db, locale, limit=50)


@router.get("/events/{event_id}/countdown")
async def countdown(event_id: int, db: AsyncSession = Depends(get_db)):
    """Countdown data comes only from a real event cutoff (PRD §12). Shown only under 72 hours."""
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    remaining = (ev.booking_cutoff_at - utcnow()).total_seconds()
    return {"event_id": ev.id, "booking_cutoff_at": ev.booking_cutoff_at.isoformat(),
            "show": 0 < remaining < 72 * 3600, "remaining_seconds": max(0, int(remaining))}


@router.get("/events/{event_id}")
async def event(event_id: int, db: AsyncSession = Depends(get_db)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    return event_dict(ev)


@router.get("/proof/{token}")
async def proof(token: str, db: AsyncSession = Depends(get_db)):
    data = await proof_page(db, token)
    if data is None:
        raise HTTPException(404, "not_found")
    return data


@router.get("/sitemap")
async def sitemap(db: AsyncSession = Depends(get_db)):
    """Every published (puja, locale) pair plus temples, for /sitemap.xml and hreflang."""
    pujas = (await db.execute(select(Puja).where(Puja.status == PublishStatus.published))).scalars().all()
    temples_ = (await db.execute(select(Temple))).scalars().all()
    return {
        "pujas": [{"id": p.id, "slug": p.slug, "kind": p.kind.value,
                   "locales": sorted(t.locale for t in p.translations if t.published)} for p in pujas],
        "temples": [{"id": t.id, "slug": t.slug, "locales": sorted(x.locale for x in t.translations)}
                    for t in temples_],
    }


class PincodeIn(BaseModel):
    pincode: str = Field(pattern=r"^\d{6}$")


@router.post("/serviceability")
async def serviceability(body: PincodeIn):
    res = await get_shipping_provider().check_serviceability(body.pincode)
    return {"serviceable": res.serviceable, "eta_days": res.eta_days}


class CallbackIn(BaseModel):
    phone_e164: str = Field(pattern=r"^\+\d{8,15}$")
    name: str | None = Field(default=None, max_length=120)
    puja_id: int | None = None
    locale: str = "en"


@router.post("/callback-requests", status_code=201)
async def callback_request(body: CallbackIn, db: AsyncSession = Depends(get_db)):
    db.add(CallbackRequest(**body.model_dump()))
    await db.commit()
    return {"ok": True}
