"""Thin wrapper around the Arq Redis pool so API code can enqueue worker jobs."""

import logging

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from config import settings

logger = logging.getLogger("jobs")
_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(function: str, *args, **kwargs) -> None:
    """Best effort: if Redis is down the worker's periodic sweeps still pick the work up from Postgres."""
    try:
        pool = await get_pool()
        await pool.enqueue_job(function, *args, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.warning("enqueue failed for %s: %s", function, e)
