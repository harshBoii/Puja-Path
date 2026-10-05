"""On-demand ISR revalidation of the Next.js storefront (PRD §3 caching rule)."""

import logging

import httpx

from config import settings

logger = logging.getLogger("revalidate")


async def revalidate(tags: list[str]) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{settings.web_internal_url}/api/revalidate",
                             json={"tags": tags}, headers={"x-revalidate-secret": settings.revalidate_secret})
            return r.status_code == 200
    except Exception as e:  # noqa: BLE001
        logger.warning("revalidate failed %s: %s", tags, e)
        return False


def puja_tags(puja_id: int) -> list[str]:
    return [f"puja:{puja_id}", "listing", "home"]
