"""Job dispatch for API code. JOBS_MODE picks how a job runs:

- inline (default): as an asyncio task inside the API process. No Redis needed.
- worker: queued in Redis for the Arq worker (apps/worker).
- manual: not run at all (tests drive jobs explicitly).
"""

import asyncio
import logging

from config import settings

logger = logging.getLogger("jobs")
_pool = None
_tasks: set[asyncio.Task] = set()  # keep references so running tasks are not garbage-collected


def redis_settings():
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool():
    global _pool
    if _pool is None:
        from arq import create_pool

        _pool = await create_pool(redis_settings())
    return _pool


async def _run_inline(function: str, args: tuple, defer: float | None) -> None:
    from services.tasks import ONE_OFF

    if defer:
        await asyncio.sleep(defer)
    try:
        await ONE_OFF[function](None, *args)
    except Exception:  # logged; periodic sweeps retry from Postgres state
        logger.exception("inline job %s failed", function)


async def enqueue(function: str, *args, **kwargs) -> None:
    """Best effort in every mode: the periodic sweeps still pick the work up from Postgres if this is lost."""
    mode = settings.jobs_mode
    if mode == "manual":
        return
    if mode == "inline":
        task = asyncio.create_task(_run_inline(function, args, kwargs.get("_defer_by")))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        return
    try:
        pool = await get_pool()
        await pool.enqueue_job(function, *args, **kwargs)
    except Exception as e:  # noqa: BLE001  (Redis down: periodic sweeps still pick the work up)
        logger.warning("enqueue failed for %s: %s", function, e)
