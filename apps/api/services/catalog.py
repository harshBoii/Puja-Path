"""Catalog reads + serialisation shared by public and admin routers."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    AddonItem,
    EventStatus,
    Package,
    Puja,
    PujaEvent,
    PujaTranslation,
    SevaPlan,
    Temple,
    TempleTranslation,
)
from providers.media.storage import public_url
from services.i18n import utcnow

PACKAGE_LABELS = {
    "individual": {"en": "Individual", "hi": "व्यक्तिगत", "ta": "தனிநபர்", "te": "వ్యక్తిగత"},
    "couple": {"en": "Couple", "hi": "दंपति", "ta": "தம்பதி", "te": "దంపతులు"},
    "family": {"en": "Family", "hi": "परिवार", "ta": "குடும்பம்", "te": "కుటుంబం"},
}


def package_label(code: str, locale: str) -> str:
    return PACKAGE_LABELS.get(code, {}).get(locale) or code.title()


def tr_for(translations: list, locale: str, *, published_only: bool = False):
    for t in translations:
        if t.locale == locale and (not published_only or getattr(t, "published", True)):
            return t
    return None


def tr_fallback(translations: list, locale: str):
    return tr_for(translations, locale) or tr_for(translations, "en") or (translations[0] if translations else None)


def image(img: dict | None, locale: str) -> dict | None:
    if not img:
        return None
    key = img.get("key")
    alt = (img.get("alt") or {}).get(locale) or (img.get("alt") or {}).get("en") or ""
    out = {"url": public_url(key), "alt": alt}
    if key and key.endswith(".webp") and not key.startswith("seed/"):
        base = key[: -len(".webp")]
        out["srcset"] = ", ".join(f"{public_url(f'{base}@{w}.webp')} {w}w" for w in (480, 960, 1440))
    if img.get("taken_on"):
        out["taken_on"] = img["taken_on"]
    return out


def temple_summary(t: Temple, locale: str) -> dict:
    tr = tr_fallback(t.translations, locale)
    return {
        "id": t.id, "slug": t.slug, "name": tr.name if tr else t.slug, "city": t.city, "state": t.state,
        "venue_type": t.venue_type.value, "presiding_deity": t.presiding_deity,
        "photo": image(t.photos[0], locale) if t.photos else None,
    }


def money(pkg: Package, currency: str) -> int:
    return pkg.price_usd_minor if currency == "USD" else pkg.price_inr_minor


def event_dict(e: PujaEvent | None) -> dict | None:
    if e is None:
        return None
    return {"id": e.id, "starts_at": e.starts_at.isoformat(), "booking_cutoff_at": e.booking_cutoff_at.isoformat(),
            "video_sla_hours": e.video_sla_hours, "status": e.status.value}


async def next_event(db: AsyncSession, puja_id: int) -> PujaEvent | None:
    return (await db.execute(
        select(PujaEvent).where(PujaEvent.puja_id == puja_id, PujaEvent.status == EventStatus.scheduled,
                                PujaEvent.booking_cutoff_at > utcnow())
        .order_by(PujaEvent.starts_at).limit(1)
    )).scalar_one_or_none()


async def upcoming_events(db: AsyncSession, puja_id: int, limit: int = 60) -> list[PujaEvent]:
    return list((await db.execute(
        select(PujaEvent).where(PujaEvent.puja_id == puja_id, PujaEvent.status == EventStatus.scheduled,
                                PujaEvent.booking_cutoff_at > utcnow())
        .order_by(PujaEvent.starts_at).limit(limit)
    )).scalars())


def puja_card(p: Puja, locale: str, ev: PujaEvent | None, currency: str) -> dict:
    tr = tr_for(p.translations, locale, published_only=True)
    active = [pk for pk in p.packages if pk.active]
    return {
        "id": p.id, "slug": p.slug, "kind": p.kind.value, "title": tr.title, "subtitle": tr.subtitle,
        "occasion_chip": tr.occasion_chip, "image": image(p.images[0], locale) if p.images else None,
        "temple": temple_summary(p.temple, locale), "event": event_dict(ev),
        "from_price_minor": min((money(pk, currency) for pk in active), default=None), "currency": currency,
        # both currencies so cached pages can show the visitor's currency client-side
        "from_prices": {"INR": min((pk.price_inr_minor for pk in active), default=None),
                        "USD": min((pk.price_usd_minor for pk in active), default=None)},
        "deity_tags": p.deity_tags, "dosha_tags": p.dosha_tags, "benefit_tags": p.benefit_tags,
    }


async def cards(db: AsyncSession, ids: list[int], locale: str, currency: str) -> list[dict]:
    """Puja cards for many ids in a constant number of queries (no per-card lookups), in the given order."""
    if not ids:
        return []
    pujas = {p.id: p for p in (await db.execute(select(Puja).where(Puja.id.in_(ids)))).scalars()}
    events = {e.puja_id: e for e in (await db.execute(
        select(PujaEvent).where(PujaEvent.puja_id.in_(ids), PujaEvent.status == EventStatus.scheduled,
                                PujaEvent.booking_cutoff_at > utcnow())
        .order_by(PujaEvent.puja_id, PujaEvent.starts_at).ext(distinct_on(PujaEvent.puja_id))
    )).scalars()}
    return [puja_card(pujas[i], locale, events.get(i), currency) for i in ids if i in pujas]


async def load_puja(db: AsyncSession, puja_id: int) -> Puja | None:
    return await db.get(Puja, puja_id)


async def puja_detail(db: AsyncSession, p: Puja, locale: str, currency: str, sla_default: int) -> dict | None:
    tr = tr_for(p.translations, locale, published_only=True)
    if tr is None:
        return None
    events = await upcoming_events(db, p.id)
    ev = events[0] if events else None
    temple = p.temple
    ttr = tr_fallback(temple.translations, locale)
    addons = (await db.execute(
        select(AddonItem).where(AddonItem.puja_id == p.id, AddonItem.active.is_(True)).order_by(AddonItem.id)
    )).scalars().all()
    seva = (await db.execute(select(SevaPlan).where(SevaPlan.puja_id == p.id))).scalar_one_or_none()
    sla = (ev.video_sla_hours if ev else None) or p.video_sla_hours or sla_default
    out = {
        **puja_card(p, locale, ev, currency),
        "about_md": tr.about_md, "benefits": tr.benefits, "rituals": tr.rituals, "faqs": tr.faqs,
        "meta_title": tr.meta_title, "meta_description": tr.meta_description,
        "images": [image(i, locale) for i in p.images[:6]],
        "facts": {"tradition": p.tradition, "duration_minutes": p.duration_minutes,
                  "priests_count": p.priests_count, "sankalp_language": p.sankalp_language},
        "requires_nakshatra": p.requires_nakshatra, "video_sla_hours": sla,
        "deliverables": p.deliverables, "prasad_box": p.prasad_box,
        "packages": [{"id": pk.id, "code": pk.code.value, "label": package_label(pk.code.value, locale),
                      "max_names": pk.max_names, "price_minor": money(pk, currency),
                      "prices": {"INR": pk.price_inr_minor, "USD": pk.price_usd_minor}}
                     for pk in p.packages if pk.active],
        "addons": [addon_dict(a, locale, currency) for a in addons],
        "temple_detail": {**temple_summary(temple, locale), "history_md": ttr.history_md if ttr else None,
                          "address": ttr.address if ttr else None, "lat": temple.lat, "lng": temple.lng,
                          "photos": [image(ph, locale) for ph in temple.photos]},
        "available_locales": sorted(t.locale for t in p.translations if t.published),
        "upcoming_events": [event_dict(e) for e in events[:12]],
    }
    if seva:
        n = seva.occurrences
        dates = events[:n]
        out["seva"] = {"rrule": seva.rrule, "occurrences": n, "autopay_allowed": seva.autopay_allowed,
                       "dates": [event_dict(e) for e in dates], "bookable": len(dates) == n}
    return out


def addon_dict(a: AddonItem, locale: str, currency: str) -> dict:
    tr = tr_fallback(a.translations, locale)
    return {"id": a.id, "name": tr.name if tr else "", "description": tr.description if tr else None,
            "image": image({"key": a.image_key, "alt": {locale: tr.name if tr else ""}}, locale) if a.image_key else None,
            "price_minor": a.price_usd_minor if currency == "USD" else a.price_inr_minor,
            "prices": {"INR": a.price_inr_minor, "USD": a.price_usd_minor},
            "max_qty": a.max_qty, "ships_home": a.ships_home}


async def puja_title(db: AsyncSession, puja_id: int, locale: str) -> str:
    rows = (await db.execute(select(PujaTranslation).where(PujaTranslation.puja_id == puja_id))).scalars().all()
    tr = tr_fallback(list(rows), locale)
    return tr.title if tr else ""


async def temple_name(db: AsyncSession, temple_id: int, locale: str) -> str:
    rows = (await db.execute(select(TempleTranslation).where(TempleTranslation.temple_id == temple_id))).scalars().all()
    tr = tr_fallback(list(rows), locale)
    return tr.name if tr else ""


def cutoff_soon(ev: PujaEvent) -> bool:
    return ev.booking_cutoff_at - utcnow() < timedelta(hours=72)
