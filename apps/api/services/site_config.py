"""site_config: the single source for every promise on the site (PRD §9).

DEFAULTS seed the table; reads always go to the table so admin edits apply everywhere at once.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import SiteConfig

DEFAULTS: dict[str, Any] = {
    "video_sla_hours_default": 48,
    "booking_cutoff_hours_default": 12,
    "support_hours": {"tz": "Asia/Kolkata", "start": "08:00", "end": "20:00", "days": [0, 1, 2, 3, 4, 5, 6]},
    "support_languages": ["te", "hi", "ta", "en"],
    "support_phone_e164": "+919000000000",
    "whatsapp_number_e164": "+919000000000",
    "gotra_fallback": {"en": "Kashyapa", "te": "కశ్యప", "hi": "कश्यप", "ta": "காஷ்யப"},
    "trust_bar_thresholds": {"pujas_completed": 100, "devotees": 100, "reviews": 25},
    "quiet_hours": {"start": "21:30", "end": "07:30"},
    # extensions — still one value each, read everywhere
    "proof_refund_after_days": 7,
    "proof_delay_eta_hours": 24,
    "refund_expected_days": "5-7",
    "reschedule_reply_hours": 48,
    "shipping_fee": {"INR": 9900, "USD": 300},
    "dakshina_options": {"INR": [5100, 10100, 25100], "USD": [300, 500, 1100]},
    "tax_rules": [],  # e.g. [{"label": "GST 18%", "rate_bps": 1800, "applies_to": "platform_fee"}]
    "consent_text_version": "2026-10-01",
    "hero_puja_ids": [],
    "campaign_cap_per_week": 2,
    "autopay_max_inr_minor": 1500000,
    "retention": {"proof_video_days": None, "sankalp_names_days": None},
    "social_links": {"instagram": "", "youtube": "", "facebook": ""},
    "banned_phrases": {
        "en": ["guaranteed", "100% result", "will remove", "assured result", "sure success", "cure"],
        "hi": ["गारंटी", "100% परिणाम", "निश्चित परिणाम", "पक्का फल"],
        "te": ["గ్యారంటీ", "100% ఫలితం", "ఖచ్చితమైన ఫలితం"],
        "ta": ["உத்தரவாதம்", "100% பலன்", "நிச்சய பலன்"],
    },
}

PUBLIC_KEYS = [
    "video_sla_hours_default",
    "booking_cutoff_hours_default",
    "support_hours",
    "support_languages",
    "support_phone_e164",
    "whatsapp_number_e164",
    "gotra_fallback",
    "quiet_hours",
    "proof_refund_after_days",
    "refund_expected_days",
    "reschedule_reply_hours",
    "shipping_fee",
    "dakshina_options",
    "tax_rules",
    "consent_text_version",
    "social_links",
]


async def get_all(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(SiteConfig))).scalars().all()
    out = dict(DEFAULTS)
    out.update({r.key: r.value for r in rows})
    return out


async def get(db: AsyncSession, key: str) -> Any:
    row = await db.get(SiteConfig, key)
    return row.value if row is not None else DEFAULTS.get(key)


async def set_value(db: AsyncSession, key: str, value: Any) -> None:
    stmt = insert(SiteConfig).values(key=key, value=value)
    await db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": value}))


async def seed_defaults(db: AsyncSession) -> None:
    for key, value in DEFAULTS.items():
        await db.execute(insert(SiteConfig).values(key=key, value=value).on_conflict_do_nothing())
