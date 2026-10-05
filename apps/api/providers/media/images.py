"""Resize uploads into WebP variants. Keys: <base>.webp plus <base>@480.webp / @960 / @1440."""

import tempfile
from pathlib import Path

from PIL import Image

from providers.media.storage import put_file

WIDTHS = (480, 960, 1440)


def process_image(src: Path, base_key: str) -> dict:
    img = Image.open(src)
    img = img.convert("RGB")
    width, height = img.size
    out_dir = Path(tempfile.mkdtemp())
    for w in WIDTHS:
        if w > width and w != WIDTHS[0]:
            continue
        variant = img.copy()
        variant.thumbnail((w, int(w * height / width)))
        p = out_dir / f"{w}.webp"
        variant.save(p, "WEBP", quality=80, method=5)
        put_file(p, f"{base_key}@{w}.webp", "image/webp")
    main = img.copy()
    main.thumbnail((1600, 1600))
    p = out_dir / "main.webp"
    main.save(p, "WEBP", quality=82, method=5)
    put_file(p, f"{base_key}.webp", "image/webp")
    return {"key": f"{base_key}.webp", "width": width, "height": height}
