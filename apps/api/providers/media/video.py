"""Video hosting: Cloudflare Stream (signed HLS) when configured, else the stored MP4 (dev/CI)."""

import time

import jwt

from config import settings
from providers.media.storage import public_url
from providers.messaging.http import request


def use_stream() -> bool:
    return bool(settings.cf_stream_account_id and settings.cf_stream_api_token)


async def ingest(key: str) -> str:
    """Copies a stored source file into Stream; returns a stream id ("local:<key>" in dev)."""
    if not use_stream():
        return f"local:{key}"
    resp = await request(
        "POST",
        f"https://api.cloudflare.com/client/v4/accounts/{settings.cf_stream_account_id}/stream/copy",
        headers={"Authorization": f"Bearer {settings.cf_stream_api_token}"},
        json={"url": public_url(key), "requireSignedURLs": True, "meta": {"name": key}},
    )
    return resp.json()["result"]["uid"]


def playback(stream_id: str | None, ttl_seconds: int = 6 * 3600) -> dict | None:
    if not stream_id:
        return None
    if stream_id.startswith("local:"):
        return {"type": "mp4", "url": public_url(stream_id.split(":", 1)[1])}
    token = jwt.encode(
        {"sub": stream_id, "kid": settings.cf_stream_signing_key_id, "exp": int(time.time()) + ttl_seconds},
        settings.cf_stream_signing_key_pem,
        algorithm="RS256",
        headers={"kid": settings.cf_stream_signing_key_id},
    )
    return {"type": "hls", "url": f"https://customer-{settings.cf_stream_account_id}.cloudflarestream.com/{token}/manifest/video.m3u8"}
