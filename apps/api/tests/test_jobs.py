"""JOBS_MODE=inline: background work runs inside the API with no Redis."""

import asyncio
import uuid

from sqlalchemy import select

from config import settings
from db import SessionLocal
from models import MessageLog, MessageStatus
from services import jobs, site_config, tasks
from tests.conftest import book


async def _no_quiet_hours():
    async with SessionLocal() as db:
        await site_config.set_value(db, "quiet_hours", {"start": "00:00", "end": "00:00"})
        await db.commit()


async def test_inline_enqueue_sends_without_redis(client, monkeypatch):
    await _no_quiet_hours()
    monkeypatch.setattr(settings, "jobs_mode", "inline")
    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")  # unreachable: must not be used
    res = await book(client)
    for _ in range(50):  # booking_confirmed is dispatched by an in-process task
        await asyncio.sleep(0.1)
        async with SessionLocal() as db:
            m = (await db.execute(select(MessageLog).where(MessageLog.booking_id == uuid.UUID(res["draft_id"]),
                                                           MessageLog.template_key == "booking_confirmed"))).scalar_one()
        if m.status == MessageStatus.sent:
            break
    assert m.status == MessageStatus.sent


async def test_periodic_job_runs_once_across_instances():
    """Two schedulers firing the same job at once: the advisory lock lets only one run it."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_job(ctx):
        started.set()
        await release.wait()
        return "ran"

    first = asyncio.create_task(tasks.run_locked(slow_job))
    await started.wait()
    assert await tasks.run_locked(slow_job) is None  # second instance skips while the first holds the lock
    release.set()
    assert await first == "ran"
    assert await tasks.run_locked(slow_job) == "ran"  # lock released afterwards


async def test_run_all_once_runs_every_periodic_job():
    out = await tasks.run_all_once()
    assert set(out) == {job.__name__ for job, _ in tasks.PERIODIC}
    assert not any(isinstance(v, str) and v.startswith("error") for v in out.values())


async def test_cron_endpoint_requires_secret(client, monkeypatch):
    assert (await client.post("/v1/internal/cron")).status_code == 404  # disabled without CRON_SECRET
    monkeypatch.setattr(settings, "cron_secret", "s3cret")
    assert (await client.post("/v1/internal/cron", headers={"x-cron-secret": "wrong"})).status_code == 404
    r = await client.post("/v1/internal/cron", headers={"x-cron-secret": "s3cret"})
    assert r.status_code == 200 and "dispatch_due" in r.json()


async def test_manual_mode_runs_nothing(monkeypatch):
    monkeypatch.setattr(settings, "jobs_mode", "manual")
    await jobs.enqueue("send_message", str(uuid.uuid4()))
    assert not jobs._tasks
