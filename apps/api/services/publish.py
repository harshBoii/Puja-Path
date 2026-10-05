"""Publish validation (PRD §4 SEO, §10 CMS, §12 guardrails).

Publishing a locale is blocked if any required field, meta field or template variable would render empty,
if placeholder patterns remain, or if a banned outcome-claim phrase appears.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Puja, PujaKind, SevaPlan, Temple
from services import site_config
from services.catalog import tr_for

PLACEHOLDER = re.compile(
    r"\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b|lorem ipsum|\{\{[^}]*\}\}|\(\s*adjust[^)]*\)|\[[^\]\n]*\](?!\()",
    re.IGNORECASE,
)


def _texts(tr) -> list[tuple[str, str]]:
    out = [("title", tr.title), ("subtitle", tr.subtitle), ("occasion_chip", tr.occasion_chip),
           ("about_md", tr.about_md), ("meta_title", tr.meta_title), ("meta_description", tr.meta_description)]
    for i, b in enumerate(tr.benefits or []):
        out += [(f"benefits[{i}].title", b.get("title")), (f"benefits[{i}].line", b.get("line"))]
    for i, r in enumerate(tr.rituals or []):
        out += [(f"rituals[{i}].title", r.get("title")), (f"rituals[{i}].text", r.get("text"))]
    for i, f in enumerate(tr.faqs or []):
        out += [(f"faqs[{i}].q", f.get("q")), (f"faqs[{i}].a", f.get("a"))]
    return out


async def validate_puja(db: AsyncSession, puja: Puja, locales: list[str]) -> list[dict]:
    errors: list[dict] = []

    def err(field: str, code: str, locale: str | None = None):
        errors.append({"locale": locale, "field": field, "code": code})

    for field in ("tradition", "sankalp_language"):
        if not (getattr(puja, field) or "").strip():
            err(field, "required")
    for field in ("duration_minutes", "priests_count"):
        if not getattr(puja, field):
            err(field, "required")
    if not puja.deliverables:
        err("deliverables", "required")
    if not puja.images:
        err("images", "required")
    temple = await db.get(Temple, puja.temple_id)
    if temple is None or temple.venue_type is None:
        err("temple.venue_type", "required")
    active = [p for p in puja.packages if p.active]
    if not active:
        err("packages", "required")
    for p in active:
        if p.price_inr_minor <= 0 or p.price_usd_minor <= 0:
            err(f"packages.{p.code.value}.price", "required")
    if puja.kind == PujaKind.seva:
        plan = (await db.execute(select(SevaPlan).where(SevaPlan.puja_id == puja.id))).scalar_one_or_none()
        if plan is None:
            err("seva_plan", "required")

    banned_all = await site_config.get(db, "banned_phrases")
    for loc in locales:
        tr = tr_for(puja.translations, loc)
        if tr is None:
            err("translation", "missing", loc)
            continue
        for field in ("title", "subtitle", "occasion_chip", "about_md", "meta_title", "meta_description"):
            if not (getattr(tr, field) or "").strip():
                err(field, "required", loc)
        if not tr.benefits:
            err("benefits", "required", loc)
        if not tr.rituals:
            err("rituals", "required", loc)
        if sum(1 for r in tr.rituals or [] if r.get("main")) > 1:
            err("rituals", "more_than_one_main", loc)
        # template variables: the puja and temple names render into WhatsApp templates in this locale
        if temple is not None and not tr_for(temple.translations, loc):
            err("temple.name", "template_variable_empty", loc)
        for i, img in enumerate(puja.images or []):
            if not ((img.get("alt") or {}).get(loc) or "").strip():
                err(f"images[{i}].alt", "required", loc)
        banned = [p.lower() for p in (banned_all.get(loc, []) + (banned_all.get("en", []) if loc != "en" else []))]
        for field, text in _texts(tr):
            if text is None:
                continue
            if not str(text).strip():
                err(field, "required", loc)
                continue
            if PLACEHOLDER.search(str(text)):
                err(field, "placeholder", loc)
            low = str(text).lower()
            for phrase in banned:
                hit = (re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", low) if phrase.isascii()
                       else phrase in low)
                if hit:
                    err(field, f"banned_phrase:{phrase}", loc)
    return errors
