"""Exports every WhatsApp template as a submission sheet for WATI / Gupshup (and Meta's review).

    python scripts/export_templates.py --site https://pujapath.in

Writes docs/whatsapp-templates.csv (one row per template per language: 18 x 4 = 72) and
docs/whatsapp-templates.md (the same, readable). Names follow the app's lookup: {MESSAGING_TEMPLATE_PREFIX}_{key}_{locale}.
Rerun after editing services/messaging_templates.py so the sheet never drifts from what the app sends.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.messaging_templates import LOCALES, TEMPLATE_SPECS, template_name

ROOT = Path(__file__).resolve().parents[3]
META_LANG = {"en": "en", "hi": "hi", "ta": "ta", "te": "te"}  # Meta language codes: English, Hindi, Tamil, Telugu

# Example values Meta asks for, one per {{n}} (by variable name).
SAMPLES = {
    "code": "482913", "name": "Lakshmi", "puja": "Rudrabhishekam", "temple": "Sri Mallikarjuna Swamy Temple, Srisailam",
    "datetime_ist": "8 Oct 2026, 7:00 am IST", "package": "Individual", "booking_code": "T38V8J", "amount": "₹501",
    "expiry": "30 minutes", "date": "8 Oct 2026", "new_eta": "10 Oct 2026", "courier": "Delhivery", "awb": "1234567890",
    "refund_amount": "₹501", "reference": "rfnd_9XyZ12", "expected_days": "5-7", "old_date": "8 Oct 2026",
    "new_date": "15 Oct 2026", "seva": "Nitya Deepa Seva", "mandate_reference": "MND123456", "festival": "Diwali",
}

# Link-button labels (max 25 characters). Quick-reply labels are NOT translated: the app matches the reply text
# ("Accept", "Refund", "1".."5"), and the message bodies already tell devotees which word to tap.
URL_LABELS = {
    "view_booking": {"en": "View booking", "hi": "बुकिंग देखें", "ta": "முன்பதிவைக் காண்க", "te": "బుకింగ్ చూడండి"},
    "pay": {"en": "Pay now", "hi": "अभी भुगतान करें", "ta": "இப்போது செலுத்துக", "te": "ఇప్పుడే చెల్లించండి"},
    "proof": {"en": "Watch full video", "hi": "पूरा वीडियो देखें", "ta": "முழு காணொளி", "te": "పూర్తి వీడియో చూడండి"},
    "track": {"en": "Track prasad", "hi": "प्रसाद ट्रैक करें", "ta": "பிரசாதத்தைக் கண்காணி", "te": "ప్రసాదం ట్రాక్"},
    "manage": {"en": "Manage seva", "hi": "सेवा प्रबंधित करें", "ta": "சேவையை நிர்வகி", "te": "సేవ నిర్వహించండి"},
    "pay_now": {"en": "Pay now", "hi": "अभी भुगतान करें", "ta": "இப்போது செலுத்துக", "te": "ఇప్పుడే చెల్లించండి"},
    "resume": {"en": "Continue booking", "hi": "बुकिंग जारी रखें", "ta": "முன்பதிவைத் தொடர்க", "te": "బుకింగ్ కొనసాగించండి"},
    "book": {"en": "Book now", "hi": "अभी बुक करें", "ta": "இப்போது பதிவு செய்க", "te": "ఇప్పుడే బుక్ చేయండి"},
}
# Example path after the site URL for each link button (what the app appends at send time).
URL_SAMPLES = {
    "view_booking": "en/account/bookings/3f2a9c1e-5b7d-4e2a-9c1e-5b7d4e2a9c1e",
    "pay": "en/checkout/3f2a9c1e-5b7d-4e2a-9c1e-5b7d4e2a9c1e",
    "proof": "en/proof/Xk3n9QpL2mZ8",
    "track": "en/account/bookings/3f2a9c1e-5b7d-4e2a-9c1e-5b7d4e2a9c1e",
    "manage": "en/account/subscriptions",
    "pay_now": "en/checkout/3f2a9c1e-5b7d-4e2a-9c1e-5b7d4e2a9c1e",
    "resume": "en/checkout/3f2a9c1e-5b7d-4e2a-9c1e-5b7d4e2a9c1e",
    "book": "en/pujas/1-rudrabhishekam",
}


def buttons(spec: dict, locale: str, site: str) -> tuple[str, str, str, str]:
    """(type, text, url, example url)"""
    b = spec.get("buttons")
    if not b:
        return "", "", "", ""
    if b == "copy_code":
        return "Copy code", "Copy code", "", ""
    kind, _, rest = b.partition(":")
    if kind == "quick":
        labels = {"accept": "Accept", "refund": "Refund"}
        return "Quick reply", " | ".join(labels.get(x, x) for x in rest.split(",")), "", ""
    return ("Visit website (dynamic URL)", URL_LABELS[rest][locale], f"{site}/{{{{1}}}}",
            f"{site}/{URL_SAMPLES[rest].replace('en/', f'{locale}/', 1)}")


def named(body: str, variables: list[str]) -> str:
    for i, v in enumerate(variables, 1):
        body = body.replace(f"{{{{{i}}}}}", f"{{{{{v}}}}}")
    return body


def rows(site: str) -> list[dict]:
    out = []
    for key, spec in TEMPLATE_SPECS.items():
        for loc in LOCALES:
            btype, btext, burl, bsample = buttons(spec, loc, site)
            out.append({
                "name": template_name(key, loc), "category": spec["category"].upper(), "language": META_LANG[loc],
                "header": "VIDEO (sample: any short .mp4 under 16 MB)" if spec.get("header") == "video" else "",
                "body": spec["body"][loc],
                # WATI: the app sends values by name, so placeholders must be {{name}}, {{puja}}, ...
                "body_wati": named(spec["body"][loc], spec["variables"]),
                "samples": " | ".join(f"{{{{{i}}}}} = {SAMPLES[v]}" for i, v in enumerate(spec["variables"], 1)),
                "button_type": btype, "button_text": btext, "button_url": burl, "button_url_example": bsample,
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="Production site URL used in link buttons, e.g. https://pujapath.in")
    site = ap.parse_args().site.rstrip("/")
    data = rows(site)
    docs = ROOT / "docs"
    with (docs / "whatsapp-templates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    md = ["# WhatsApp templates to submit", "",
          f"Generated by `apps/api/scripts/export_templates.py --site {site}`. {len(data)} templates "
          f"({len(TEMPLATE_SPECS)} messages x {len(LOCALES)} languages). Create each one in WATI or Gupshup with "
          "exactly this name, category, language, body and buttons. See docs/whatsapp-setup.md for the steps.", ""]
    for r in data:
        md += [f"## `{r['name']}`", "",
               f"- **Category:** {r['category']} · **Language:** {r['language']}"
               + (f" · **Header:** {r['header']}" if r["header"] else ""),
               f"- **Body (Gupshup):** {r['body']}", f"- **Body (WATI):** {r['body_wati']}",
               f"- **Sample values:** {r['samples']}"]
        if r["button_type"]:
            md.append(f"- **Button:** {r['button_type']}: \"{r['button_text']}\""
                      + (f" → `{r['button_url']}` (example `{r['button_url_example']}`)" if r["button_url"] else ""))
        md.append("")
    (docs / "whatsapp-templates.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {len(data)} templates to docs/whatsapp-templates.csv and docs/whatsapp-templates.md")


if __name__ == "__main__":
    main()
