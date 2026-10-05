"""Seeds site_config, WhatsApp templates, the bootstrap admin and the demo catalog. Idempotent.

Usage: uv run python seed.py [--catalog]   (catalog is skipped if pujas already exist)
"""

import asyncio
import sys
from datetime import datetime, time, timedelta

from sqlalchemy import func, select

from config import settings
from db import SessionLocal
from models import (
    AddonItem,
    AddonItemTranslation,
    EventStatus,
    FaqEntry,
    Package,
    PackageCode,
    PublishStatus,
    Puja,
    PujaEvent,
    PujaKind,
    PujaTranslation,
    SevaPlan,
    StaffRole,
    StaffUser,
    Temple,
    TempleTranslation,
    VenueType,
)
from security import hash_password
from seed_content import ADDON_NAMES, FAQS, IMG, PUJAS, TEMPLES
from services import site_config
from services.i18n import IST, utcnow
from services.messaging_templates import seed_templates
from services.publish import validate_puja

LOCALES = ("en", "hi", "ta", "te")


async def seed_base(db) -> None:
    await site_config.seed_defaults(db)
    await seed_templates(db)
    if settings.admin_email and settings.admin_password:
        exists = (await db.execute(select(StaffUser).where(StaffUser.email == settings.admin_email))).scalar_one_or_none()
        if exists is None:
            db.add(StaffUser(email=settings.admin_email.lower(), name="Admin", role=StaffRole.admin,
                             password_hash=hash_password(settings.admin_password), active=True))
            print(f"created admin {settings.admin_email} (TOTP enrolment on first login)")
    await db.commit()


def _at(days: int, hour: int, minute: int) -> datetime:
    d = utcnow().astimezone(IST).date() + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=IST)


async def seed_catalog(db) -> None:
    if (await db.execute(select(func.count()).select_from(Puja))).scalar():
        print("catalog exists; skipping")
        return
    cutoff_h = await site_config.get(db, "booking_cutoff_hours_default")
    sla_default = await site_config.get(db, "video_sla_hours_default")
    temples = []
    for t in TEMPLES:
        temple = Temple(slug=t["slug"], city=t["city"], state=t["state"], lat=t["lat"], lng=t["lng"],
                        presiding_deity=t["presiding_deity"], venue_type=VenueType(t["venue_type"]), photos=t["photos"])
        temple.translations = [TempleTranslation(locale=loc, name=v[0], address=v[1], history_md=v[2])
                               for loc, v in t["tr"].items()]
        db.add(temple)
        temples.append(temple)
    await db.flush()

    hero = []
    for spec in PUJAS:
        p = Puja(
            temple_id=temples[spec["temple"]].id, slug=spec["slug"], kind=PujaKind(spec["kind"]),
            deity_tags=spec["deity_tags"], dosha_tags=spec["dosha_tags"], benefit_tags=spec["benefit_tags"],
            tradition=spec["tradition"], duration_minutes=spec["duration_minutes"],
            priests_count=spec["priests_count"], sankalp_language=spec["sankalp_language"],
            requires_nakshatra=spec["requires_nakshatra"], video_sla_hours=spec.get("video_sla_hours"),
            deliverables=spec["deliverables"], prasad_box=spec["prasad_box"],
            images=[{"key": IMG.format(i), "alt": spec["image_alt"]} for i in spec["images"]],
            status=PublishStatus.draft,
        )
        locales = spec.get("locales", LOCALES)
        p.translations = [PujaTranslation(locale=loc, published=False, **spec["tr"][loc]) for loc in locales]
        db.add(p)
        await db.flush()
        for code, (inr, usd), n in zip(("individual", "couple", "family"), spec["prices"], (1, 2, 4), strict=True):
            db.add(Package(puja_id=p.id, code=PackageCode(code), max_names=n, price_inr_minor=inr,
                           price_usd_minor=usd, active=True))
        names = {**ADDON_NAMES, **spec.get("addon_names", {})}
        for key, inr, usd, max_qty, ships_home, _alt in spec["addons"]:
            item = AddonItem(puja_id=p.id, image_key=IMG.format(key), price_inr_minor=inr, price_usd_minor=usd,
                             max_qty=max_qty, ships_home=ships_home, active=True)
            item.translations = [AddonItemTranslation(locale=loc, name=names[key][loc]) for loc in LOCALES]
            db.add(item)
        sla = spec.get("video_sla_hours") or sla_default
        if "seva" in spec:
            s = spec["seva"]
            db.add(SevaPlan(puja_id=p.id, rrule=s["rrule"], occurrences=s["occurrences"], autopay_allowed=True))
            start = utcnow().astimezone(IST).date() + timedelta(days=1)
            if s["first_weekday"] is not None:
                while start.weekday() != s["first_weekday"]:
                    start += timedelta(days=1)
            step = 7 if "WEEKLY" in s["rrule"] else 1
            for i in range(s["count"]):
                st = datetime.combine(start + timedelta(days=step * i), time(s["hour"], s["minute"]), tzinfo=IST)
                db.add(PujaEvent(puja_id=p.id, starts_at=st, booking_cutoff_at=st - timedelta(hours=cutoff_h),
                                 video_sla_hours=sla, status=EventStatus.scheduled))
        else:
            for days, hour, minute in spec["events"]:
                st = _at(days, hour, minute)
                db.add(PujaEvent(puja_id=p.id, starts_at=st, booking_cutoff_at=st - timedelta(hours=cutoff_h),
                                 video_sla_hours=sla, status=EventStatus.scheduled))
        await db.flush()
        p = (await db.execute(select(Puja).where(Puja.id == p.id)
                              .execution_options(populate_existing=True))).scalar_one()
        errors = await validate_puja(db, p, list(locales))
        if errors:
            print(f"!! {spec['key']} not published: {errors}")
            continue
        p.status = PublishStatus.published
        for t in p.translations:
            t.published = True
        if spec["kind"] == "one_time" and len(hero) < 4:
            hero.append(p.id)
    for loc, items in FAQS.items():
        for i, (q, a) in enumerate(items):
            db.add(FaqEntry(locale=loc, position=i, question=q, answer_md=a))
    await site_config.set_value(db, "hero_puja_ids", hero)
    await db.commit()
    print(f"seeded {len(TEMPLES)} temples, {len(PUJAS)} pujas, hero={hero}")


async def main() -> None:
    async with SessionLocal() as db:
        await seed_base(db)
        if "--catalog" in sys.argv or "--all" in sys.argv:
            await seed_catalog(db)


if __name__ == "__main__":
    asyncio.run(main())
