"""Replace the demo SVG artwork with real photos from Pexels.

    PEXELS_API_KEY=... uv run python scripts/fetch_images.py            # download + process, writes seed_images.json
    uv run python scripts/fetch_images.py --apply                       # write the images into the database

Where images go:
- Cloudflare R2 when R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_BUCKET / R2_PUBLIC_BASE_URL are set;
- otherwise apps/web/public/images/photos/ (served by the website itself, works on Vercel).

Each photo gets WebP variants (@480/@960/@1440 + main), alt text in en/hi/ta/te describing the subject, and a credit
(photographer + Pexels URL) saved in seed_images.json and apps/web/public/images/photos/CREDITS.json.
These are stand-in photos for the demo catalog: replace them with partner-temple photography before launch.
"""

import argparse
import asyncio
import io
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
from PIL import Image

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

from config import settings  # noqa: E402

WEB_PHOTOS = API_DIR.parent / "web" / "public" / "images" / "photos"
MANIFEST = API_DIR / "seed_images.json"
WIDTHS = (480, 960, 1440)


def alt(en, hi, ta, te):
    return {"en": en, "hi": hi, "ta": ta, "te": te}


A = {
    "lamp": alt("A lit oil lamp", "जलता हुआ दीपक", "ஏற்றப்பட்ட எண்ணெய் விளக்கு", "వెలిగించిన నూనె దీపం"),
    "flowers": alt("Flower offerings", "फूलों का अर्पण", "மலர் காணிக்கைகள்", "పూల సమర్పణలు"),
    "fire": alt("A sacred fire ritual", "पवित्र अग्नि अनुष्ठान", "புனித அக்னிச் சடங்கு", "పవిత్ర అగ్ని క్రతువు"),
    "bells": alt("Brass temple bells", "पीतल की मंदिर घंटियाँ", "பித்தளைக் கோவில் மணிகள்", "ఇత్తడి ఆలయ గంటలు"),
    "ghat": alt("Steps of a ghat on the river", "नदी किनारे घाट की सीढ़ियाँ", "நதிக்கரைப் படித்துறையின் படிகள்", "నది ఒడ్డున ఘాట్ మెట్లు"),
    "aarti": alt("An evening aarti on the river", "नदी पर संध्या आरती", "நதிக்கரையில் மாலை ஆரத்தி", "నదిపై సాయంత్రం హారతి"),
    "gopuram": alt("A temple gopuram", "मंदिर का गोपुरम", "கோவில் கோபுரம்", "ఆలయ గోపురం"),
    "temple": alt("A temple shrine", "मंदिर का गर्भगृह", "கோவில் சன்னதி", "ఆలయ సన్నిధి"),
    "lotus": alt("A lotus flower", "कमल का फूल", "தாமரைப் பூ", "కమల పుష్పం"),
    "thali": alt("A puja plate with offerings", "अर्पण सहित पूजा की थाली", "காணிக்கைகளுடன் பூஜைத் தட்டு", "సమర్పణలతో పూజా పళ్లెం"),
    "oil": alt("Sesame oil", "तिल का तेल", "நல்லெண்ணெய்", "నువ్వుల నూనె"),
    "cloth": alt("Black cloth", "काला वस्त्र", "கருப்பு வஸ்திரம்", "నల్ల వస్త్రం"),
    "til": alt("Black sesame seeds", "काले तिल", "கருப்பு எள்", "నల్ల నువ్వులు"),
    "coconut": alt("A coconut", "नारियल", "தேங்காய்", "కొబ్బరికాయ"),
    "lingam": alt("A Shiva lingam decorated with marigolds", "गेंदे के फूलों से सजा शिवलिंग",
                  "சாமந்திப் பூக்களால் அலங்கரிக்கப்பட்ட சிவலிங்கம்", "బంతి పూలతో అలంకరించిన శివలింగం"),
}

# target -> list of (pexels query, alt key). Objects and places, not deity close-ups (badges sit on image corners).
TARGETS = {
    "puja:rudrabhishekam": [("shiva lingam temple", "lingam"), ("brass temple bells", "bells")],
    "puja:navagraha-shanti-homam": [("havan fire ritual", "fire"), ("diya lamps", "lamp")],
    "puja:pitru-tarpan": [("varanasi ghat", "ghat"), ("ganga aarti", "aarti")],
    "puja:lakshmi-kubera-puja": [("pink lotus flower", "lotus"), ("puja thali", "thali")],
    "puja:rahu-ketu-shanti-puja": [("fire ritual india", "fire")],
    "puja:satyanarayana-vratam": [("marigold flowers offering", "flowers"), ("puja thali", "thali")],
    "puja:shani-chadhava": [("oil lamp temple", "lamp")],
    "puja:mangalavara-hanuman-seva": [("temple bells india", "bells")],
    "puja:nitya-deepa-seva": [("diya oil lamp", "lamp")],
    "temple:sri-mallikarjuna-swamy-temple-vijayawada": [("south indian temple gopuram", "gopuram")],
    "temple:navagraha-yagashala-kanchipuram": [("havan kund fire", "fire")],
    "temple:dashashwamedh-ghat-varanasi": [("varanasi ghat steps", "ghat")],
    "temple:sri-mahalakshmi-temple-hyderabad": [("hindu temple interior", "temple")],
    "addon:addon-oil": [("oil in brass bowl", "oil")],
    "addon:addon-cloth": [("black fabric", "cloth")],
    "addon:addon-til": [("black sesame seeds", "til")],
    "addon:addon-diya": [("clay diya", "lamp")],
    "addon:addon-flowers": [("marigold flowers", "flowers")],
    "addon:addon-coconut": [("coconut", "coconut")],
}


def use_r2() -> bool:
    return all([settings.r2_account_id, settings.r2_access_key_id, settings.r2_secret_access_key, settings.r2_bucket,
                settings.r2_public_base_url])


def save_variants(img: Image.Image, name: str) -> str:
    """Writes main + width variants; returns the key the site stores (R2 key, or /images/photos/... path)."""
    img = img.convert("RGB")
    w, h = img.size
    out = Path(tempfile.mkdtemp())
    files = {}
    for width in WIDTHS:
        v = img.copy()
        v.thumbnail((width, int(width * h / w)))
        files[f"{name}@{width}.webp"] = v
    main = img.copy()
    main.thumbnail((1600, 1600))
    files[f"{name}.webp"] = main
    if use_r2():
        from providers.media.storage import public_url, put_file

        for fname, im in files.items():
            p = out / fname
            im.save(p, "WEBP", quality=80, method=5)
            put_file(p, f"photos/{fname}", "image/webp")
        # store the full public URL so the site shows photos regardless of the API's R2 settings
        return public_url(f"photos/{name}.webp")
    WEB_PHOTOS.mkdir(parents=True, exist_ok=True)
    for fname, im in files.items():
        im.save(WEB_PHOTOS / fname, "WEBP", quality=80, method=5)
    return f"/images/photos/{name}.webp"


async def fetch(key: str, only: list[str] | None = None, skip: int = 0) -> dict:
    """Fetches every target, or just `only` (merged into the existing manifest). `skip` passes over the first N
    results, for when a query's top hit is off-topic."""
    manifest: dict[str, list] = json.loads(MANIFEST.read_text()) if only and MANIFEST.exists() else {}
    targets = {t: q for t, q in TARGETS.items() if not only or t in only}
    used: set[str] = {im["credit"]["url"] for t, ims in manifest.items() if t not in targets for im in ims}
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": key}) as client:
        for target, queries in targets.items():
            manifest[target] = []
            for i, (query, alt_key) in enumerate(queries):
                r = await client.get("https://api.pexels.com/v1/search",
                                     params={"query": query, "per_page": 15, "orientation": "landscape"})
                r.raise_for_status()
                candidates = [p for p in r.json().get("photos", []) if p["url"] not in used][skip:]
                photo = candidates[0] if candidates else None
                if photo is None:
                    print(f"  ! no photo for {target} / {query}")
                    continue
                used.add(photo["url"])
                data = (await client.get(photo["src"]["large2x"])).content
                # photo id in the name: a replacement is a new URL, so long-cached old images never linger
                name = f"{target.split(':', 1)[1]}-{i + 1}-{photo['id']}"
                stored = save_variants(Image.open(io.BytesIO(data)), name)
                manifest[target].append({
                    "key": stored, "alt": A[alt_key],
                    "credit": {"photographer": photo["photographer"], "url": photo["url"], "source": "Pexels"},
                })
                print(f"  {target:55s} {stored}  (photo by {photo['photographer']})")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    credits = [{"image": im["key"], **im["credit"]} for items in manifest.values() for im in items]
    WEB_PHOTOS.mkdir(parents=True, exist_ok=True)
    (WEB_PHOTOS / "CREDITS.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2))
    print(f"\n{len(credits)} photos -> {'R2' if use_r2() else WEB_PHOTOS}; manifest: {MANIFEST.name}")
    return manifest


async def apply(manifest: dict) -> None:
    from sqlalchemy import or_, select

    from db import SessionLocal
    from models import AddonItem, Puja, Temple
    from services.revalidate import revalidate

    tags: list[str] = ["home", "listing"]
    async with SessionLocal() as db:
        n = 0
        for target, images in manifest.items():
            if not images:
                continue
            kind, slug = target.split(":", 1)
            if kind == "puja":
                p = (await db.execute(select(Puja).where(Puja.slug == slug))).scalar_one_or_none()
                if p:
                    p.images = [{"key": im["key"], "alt": im["alt"], "credit": im["credit"]} for im in images]
                    tags.append(f"puja:{p.id}")
                    n += 1
            elif kind == "temple":
                t = (await db.execute(select(Temple).where(Temple.slug == slug))).scalar_one_or_none()
                if t:  # stock photos: no taken_on date, so they never appear as real event/gallery photos
                    t.photos = [{"key": im["key"], "alt": im["alt"], "credit": im["credit"]} for im in images]
                    tags.append(f"temple:{t.id}")
                    n += 1
            else:
                for item in (await db.execute(select(AddonItem).where(or_(
                        AddonItem.image_key == f"/images/seed/{slug}.svg",
                        AddonItem.image_key.like(f"%photos/{slug}-%"))))).scalars():
                    item.image_key = images[0]["key"]
                    n += 1
        await db.commit()
    print(f"updated {n} records")
    await revalidate(tags)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write images from seed_images.json into the database")
    ap.add_argument("--only", nargs="+", help="re-fetch just these targets, e.g. addon:addon-oil")
    ap.add_argument("--skip", type=int, default=0, help="skip the first N search results")
    args = ap.parse_args()
    if args.apply:
        if not MANIFEST.exists():
            sys.exit("seed_images.json not found: run without --apply first")
        asyncio.run(apply(json.loads(MANIFEST.read_text())))
        return
    key = os.environ.get("PEXELS_API_KEY") or settings.pexels_api_key
    if not key:
        sys.exit("Set PEXELS_API_KEY (from https://www.pexels.com/api/)")
    asyncio.run(fetch(key, args.only, args.skip))


if __name__ == "__main__":
    main()
