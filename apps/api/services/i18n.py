"""Locale + time helpers shared by messages, PDFs and the API."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from babel.dates import format_date, format_datetime
from babel.numbers import format_currency

LOCALES = ("en", "hi", "ta", "te")
IST = ZoneInfo("Asia/Kolkata")
_BABEL = {"en": "en_IN", "hi": "hi_IN", "ta": "ta_IN", "te": "te_IN"}

# Country calling code -> a representative time zone (quiet hours, reminder time).
_TZ_BY_PREFIX = [
    ("+91", "Asia/Kolkata"), ("+971", "Asia/Dubai"), ("+966", "Asia/Riyadh"), ("+974", "Asia/Qatar"),
    ("+965", "Asia/Kuwait"), ("+968", "Asia/Muscat"), ("+973", "Asia/Bahrain"), ("+65", "Asia/Singapore"),
    ("+60", "Asia/Kuala_Lumpur"), ("+44", "Europe/London"), ("+61", "Australia/Sydney"),
    ("+64", "Pacific/Auckland"), ("+49", "Europe/Berlin"), ("+33", "Europe/Paris"), ("+31", "Europe/Amsterdam"),
    ("+1", "America/New_York"), ("+977", "Asia/Kathmandu"), ("+94", "Asia/Colombo"),
]


def tz_for_phone(phone_e164: str | None, override: str | None = None) -> ZoneInfo:
    if override:
        try:
            return ZoneInfo(override)
        except Exception:  # noqa: BLE001  (bad stored zone -> fall back to phone prefix)
            pass
    for prefix, tz in sorted(_TZ_BY_PREFIX, key=lambda p: -len(p[0])):
        if phone_e164 and phone_e164.startswith(prefix):
            return ZoneInfo(tz)
    return IST


def fmt_dt_ist(dt: datetime, locale: str) -> str:
    return format_datetime(dt.astimezone(IST), "d MMM y, h:mm a", locale=_BABEL.get(locale, "en_IN")) + " IST"


def fmt_date(dt: datetime, locale: str, tz: ZoneInfo = IST) -> str:
    return format_date(dt.astimezone(tz), "EEE, d MMM y", locale=_BABEL.get(locale, "en_IN"))


def fmt_money(minor: int, currency: str, locale: str) -> str:
    return format_currency(minor / 100, currency, locale=_BABEL.get(locale, "en_IN"),
                           format_type="standard", currency_digits=False).replace(".00", "")


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_quiet_hours(now_utc: datetime, tz: ZoneInfo, quiet: dict) -> datetime | None:
    """If `now` is inside quiet hours for `tz`, returns the UTC time they end; else None."""
    start, end = parse_hhmm(quiet["start"]), parse_hhmm(quiet["end"])
    local = now_utc.astimezone(tz)
    t = local.time()
    inside = (t >= start or t < end) if start > end else (start <= t < end)
    if not inside:
        return None
    end_day = local.date() if t < end else local.date() + timedelta(days=1)
    return datetime.combine(end_day, end, tzinfo=tz).astimezone(UTC)


def reminder_time(event_start: datetime, tz: ZoneInfo) -> datetime:
    """18:00 recipient-local on the day before the puja's local date."""
    local_day = event_start.astimezone(tz).date() - timedelta(days=1)
    return datetime.combine(local_day, time(18, 0), tzinfo=tz).astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)
