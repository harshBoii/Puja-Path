"""Submits the app's WhatsApp templates to Meta for approval, so nobody has to type 72 of them by hand.

Templates are created on your WhatsApp Business Account through Meta's WhatsApp Business Management API. WATI and
Gupshup both run on that account, so the templates appear in their dashboards too. Afterwards use
Admin → Messaging → Sync templates.

    export META_ACCESS_TOKEN=...   # system-user token with whatsapp_business_management permission
    export META_WABA_ID=...        # WhatsApp Business Account ID (WhatsApp Manager → Account tools)
    export META_APP_ID=...         # only for the video sample of proof_video (any app in your business)

    python scripts/create_templates.py --site https://pujapath.in --dry-run                 # print, send nothing
    python scripts/create_templates.py --site https://pujapath.in --essential --locales en  # 8 to start
    python scripts/create_templates.py --site https://pujapath.in --video sample.mp4        # everything

Already-existing templates (same name and language) are skipped, so it is safe to rerun.
Placeholders: WATI sends values by name, so the default for MESSAGING_PROVIDER=wati is named ({{name}}).
Gupshup sends them in order: use --format positional ({{1}}).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_templates import SAMPLES, URL_LABELS, URL_SAMPLES, named

from config import settings
from services.messaging_templates import LOCALES, TEMPLATE_SPECS

GRAPH = "https://graph.facebook.com/v21.0"
ESSENTIAL = ["otp_login", "booking_confirmed", "puja_reminder", "puja_started", "proof_video", "proof_delayed",
             "booking_cancelled", "refund_processed"]
OTP_MINUTES = 10  # routers/auth.py OTP_TTL


def payload(key: str, locale: str, site: str, fmt: str, video_handle: str | None) -> dict:
    spec = TEMPLATE_SPECS[key]
    name = f"pp_{key}_{locale}"
    if spec["category"] == "authentication":
        # Meta writes authentication text itself (localized); we only choose the extras and the copy button.
        return {"name": name, "language": locale, "category": "AUTHENTICATION", "components": [
            {"type": "BODY", "add_security_recommendation": True},
            {"type": "FOOTER", "code_expiration_minutes": OTP_MINUTES},
            {"type": "BUTTONS", "buttons": [{"type": "OTP", "otp_type": "COPY_CODE"}]},
        ]}
    variables = spec["variables"]
    body = spec["body"][locale]
    if fmt == "named":
        body_c = {"type": "BODY", "text": named(body, variables), "example": {
            "body_text_named_params": [{"param_name": v, "example": SAMPLES[v]} for v in variables]}}
    else:
        body_c = {"type": "BODY", "text": body, "example": {"body_text": [[SAMPLES[v] for v in variables]]}}
    components: list[dict] = []
    if spec.get("header") == "video":
        if not video_handle:
            raise ValueError("needs --video (a sample .mp4 for the video header)")
        components.append({"type": "HEADER", "format": "VIDEO", "example": {"header_handle": [video_handle]}})
    components.append(body_c)
    b = spec.get("buttons")
    if b:
        kind, _, rest = b.partition(":")
        if kind == "url":
            sample = f"{site}/{URL_SAMPLES[rest].replace('en/', f'{locale}/', 1)}"
            buttons = [{"type": "URL", "text": URL_LABELS[rest][locale], "url": f"{site}/{{{{1}}}}", "example": [sample]}]
        else:  # quick replies: the app matches these exact words
            labels = {"accept": "Accept", "refund": "Refund"}
            buttons = [{"type": "QUICK_REPLY", "text": labels.get(x, x)} for x in rest.split(",")]
        components.append({"type": "BUTTONS", "buttons": buttons})
    return {"name": name, "language": locale, "category": spec["category"].upper(),
            "parameter_format": fmt.upper(), "components": components}


def upload_sample_video(client: httpx.Client, path: Path, app_id: str) -> str:
    """Meta's resumable upload: returns the handle a template uses as its header example."""
    data = path.read_bytes()
    r = client.post(f"{GRAPH}/{app_id}/uploads", params={
        "file_name": path.name, "file_length": len(data), "file_type": "video/mp4"})
    r.raise_for_status()
    token = client.headers["Authorization"].removeprefix("Bearer ")
    # This step wants "OAuth <token>", per Meta's resumable upload docs.
    r = client.post(f"{GRAPH}/{r.json()['id']}", content=data, headers={"Authorization": f"OAuth {token}", "file_offset": "0"})
    r.raise_for_status()
    return r.json()["h"]


def existing(client: httpx.Client, waba: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    url, params = f"{GRAPH}/{waba}/message_templates", {"fields": "name,language", "limit": 200}
    while url:
        r = client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        out |= {(t["name"], t["language"]) for t in data.get("data", [])}
        url, params = data.get("paging", {}).get("next"), None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="production site URL for link buttons, e.g. https://pujapath.in")
    ap.add_argument("--locales", default=",".join(LOCALES), help="comma list, e.g. en or en,hi")
    ap.add_argument("--only", help="comma list of message types (default: all 18)")
    ap.add_argument("--essential", action="store_true", help=f"only the {len(ESSENTIAL)} needed for every booking")
    ap.add_argument("--format", choices=["named", "positional"],
                    default="positional" if settings.messaging_provider == "gupshup" else "named")
    ap.add_argument("--video", type=Path, help="sample .mp4 (under 16 MB) for proof_video's header")
    ap.add_argument("--dry-run", action="store_true", help="print the requests, send nothing")
    a = ap.parse_args()
    site = a.site.rstrip("/")
    keys = ESSENTIAL if a.essential else (a.only.split(",") if a.only else list(TEMPLATE_SPECS))
    locales = [x for x in a.locales.split(",") if x]
    unknown = [k for k in keys if k not in TEMPLATE_SPECS] + [x for x in locales if x not in LOCALES]
    if unknown:
        sys.exit(f"unknown: {unknown}")

    if a.dry_run:
        for k in keys:
            for loc in locales:
                try:
                    print(json.dumps(payload(k, loc, site, a.format, "<video handle>"), ensure_ascii=False))
                except ValueError as e:
                    print(f"skip pp_{k}_{loc}: {e}")
        return

    token, waba = os.environ.get("META_ACCESS_TOKEN"), os.environ.get("META_WABA_ID")
    if not token or not waba:
        sys.exit("set META_ACCESS_TOKEN and META_WABA_ID (see the top of this file)")
    with httpx.Client(timeout=60, headers={"Authorization": f"Bearer {token}"}) as client:
        handle = None
        if a.video and "proof_video" in keys:
            app_id = os.environ.get("META_APP_ID") or sys.exit("set META_APP_ID to upload the sample video")
            handle = upload_sample_video(client, a.video, app_id)
        have = existing(client, waba)
        created = skipped = failed = 0
        for k in keys:
            for loc in locales:
                name = f"pp_{k}_{loc}"
                if (name, loc) in have:
                    print(f"exists   {name}")
                    skipped += 1
                    continue
                try:
                    body = payload(k, loc, site, a.format, handle)
                except ValueError as e:
                    print(f"skipped  {name}: {e}")
                    skipped += 1
                    continue
                r = client.post(f"{GRAPH}/{waba}/message_templates", json=body)
                if r.is_success:
                    print(f"sent     {name}: {r.json().get('status', '')}")
                    created += 1
                else:
                    err = r.json().get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
                    print(f"FAILED   {name}: {err.get('error_user_msg') or err.get('message') or r.text[:200]}")
                    failed += 1
                time.sleep(0.5)  # stay well under Meta's template-creation rate limit
    print(f"\n{created} submitted for review, {skipped} skipped, {failed} failed. "
          "Then: Admin → Messaging → Sync templates.")


if __name__ == "__main__":
    main()
