"""Background jobs, shared by both execution modes (JOBS_MODE):

- worker: Arq + Redis. apps/worker/worker.py registers these functions and the PERIODIC schedule as cron jobs.
- inline: no Redis, no worker process. `services.jobs.enqueue` runs one-off jobs as asyncio tasks inside the API, and
  `run_scheduler()` (started from the API lifespan) runs PERIODIC jobs on timers.
- manual: nothing runs automatically (tests drive jobs explicitly).

Every function takes Arq's `ctx` first so the same callable works in both modes (inline passes None).
"""

import asyncio
import logging
import time
import zlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from db import SessionLocal, engine
from logging_setup import log
from services import bookings as booking_svc
from services import events as event_svc
from services import maintenance, notify, seva, sla
from services import proof as proof_svc
from services.revalidate import puja_tags, revalidate

logger = logging.getLogger("tasks")


# ---------------------------------------------------------------- one-off jobs
async def send_message(ctx, message_id: str) -> str:
    return await notify.send_one(message_id)


async def cut_clips(ctx, event_id: int) -> int:
    from models import PujaEvent

    async with SessionLocal() as db:
        ev = await db.get(PujaEvent, event_id)
        n = await proof_svc.cut_event_clips(db, ev)
        await db.commit()
        return n


async def fake_payment_webhook(ctx, event: dict) -> dict:
    from routers.dev import deliver

    return await deliver(event)


# ---------------------------------------------------------------- periodic jobs
async def dispatch_due(ctx) -> int:
    """Picks up scheduled, held (quiet hours) and retrying messages."""
    from services.jobs import enqueue

    async with SessionLocal() as db:
        ids = await notify.due_message_ids(db)
    for mid in ids:
        await enqueue("send_message", mid, _job_id=f"msg:{mid}:{int(time.time() // 15)}")
    return len(ids)


async def lock_events(ctx) -> list[int]:
    async with SessionLocal() as db:
        locked = await event_svc.lock_due_events(db)
        await notify.commit_and_dispatch(db)
        pujas = set()
        if locked:
            from models import PujaEvent

            for eid in locked:
                ev = await db.get(PujaEvent, eid)
                pujas.add(ev.puja_id)
    for pid in pujas:  # a puja leaves listings at its cutoff
        await revalidate(puja_tags(pid))
    return locked


async def expire_payments(ctx) -> int:
    async with SessionLocal() as db:
        n = await booking_svc.expire_unpaid(db)
        await db.commit()
        return n


async def reschedule_defaults(ctx) -> int:
    async with SessionLocal() as db:
        n = await event_svc.auto_accept_reschedules(db)
        await notify.commit_and_dispatch(db)
        return n


async def sla_check(ctx) -> int:
    async with SessionLocal() as db:
        n = await sla.check_breaches(db)
        await notify.commit_and_dispatch(db)
        return n


async def autopay(ctx) -> dict:
    async with SessionLocal() as db:
        stats = await seva.autopay_tick(db)
        await notify.commit_and_dispatch(db)
        return stats


async def checkout_reminders(ctx) -> int:
    """1 hour after an abandoned checkout, marketing opt-in only (send_one enforces consent)."""
    from models import Booking, BookingStatus, User
    from services.catalog import puja_title
    from services.i18n import utcnow

    async with SessionLocal() as db:
        now = utcnow()
        rows = (await db.execute(select(Booking).where(
            Booking.status.in_([BookingStatus.draft, BookingStatus.cancelled]), Booking.user_id.is_not(None),
            Booking.subscription_id.is_(None), Booking.created_at < now - timedelta(hours=1),
            Booking.created_at > now - timedelta(hours=6),
        ))).scalars().all()
        n = 0
        for b in rows:
            if b.status == BookingStatus.cancelled and b.cancel_reason != "payment_expired":
                continue
            user = await db.get(User, b.user_id)
            if not user or not user.marketing_opt_in_at or b.event.booking_cutoff_at <= now:
                continue
            path = f"{b.locale}/checkout/{b.id}"
            if b.status == BookingStatus.cancelled:
                path = f"{b.locale}/pujas/{b.event.puja_id}-{b.event.puja.slug}"
            if await notify.queue(db, template_key="checkout_reminder", to=b.whatsapp_e164 or user.phone_e164,
                                  locale=b.locale, booking=b, params=[b.names[0].name if b.names else (user.name or ""),
                                                                      await puja_title(db, b.event.puja_id, b.locale)],
                                  button_params=[path]):
                n += 1
        await notify.commit_and_dispatch(db)
        return n


async def daily_reconcile(ctx) -> int:
    async with SessionLocal() as db:
        n = await maintenance.reconcile(db)
        await db.commit()
        return n


async def daily_purge(ctx) -> dict:
    async with SessionLocal() as db:
        stats = await maintenance.purge(db)
        await db.commit()
        return stats


ONE_OFF = {f.__name__: f for f in (send_message, cut_clips, fake_payment_webhook)}

# (job, every N seconds) — the same cadence the Arq worker uses.
PERIODIC = [
    (dispatch_due, 15),
    (lock_events, 30),
    (expire_payments, 120),
    (reschedule_defaults, 600),
    (sla_check, 600),
    (autopay, 300),
    (checkout_reminders, 600),
]
# (job, UTC hour, UTC minute) — once a day.
DAILY = [(daily_reconcile, 1, 30), (daily_purge, 21, 0)]


# ---------------------------------------------------------------- inline execution
async def run_locked(job) -> object | None:
    """Runs a job only if no other API instance is running it right now (transaction-scoped advisory lock,
    which also works through Neon's pgbouncer pooler). Returns None when skipped."""
    key = zlib.crc32(job.__name__.encode())
    async with engine.connect() as conn, conn.begin():
        if not await conn.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": key}):
            return None
        return await job(None)


async def run_all_once() -> dict:
    """Runs every periodic job once (for an external cron hitting /v1/internal/cron on serverless hosts)."""
    out = {}
    for job, _ in PERIODIC:
        try:
            out[job.__name__] = await run_locked(job)
        except Exception as e:
            logger.exception("job %s failed", job.__name__)
            out[job.__name__] = f"error: {e}"
    return out


async def _every(job, seconds: int) -> None:
    while True:
        started = time.monotonic()
        try:
            await run_locked(job)
        except Exception:  # a failing job must not stop the scheduler
            logger.exception("job %s failed", job.__name__)
        await asyncio.sleep(max(1.0, seconds - (time.monotonic() - started)))


async def _daily(job, hour: int, minute: int) -> None:
    while True:
        now = datetime.now(UTC)
        nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        await asyncio.sleep((nxt - now).total_seconds())
        try:
            await run_locked(job)
        except Exception:
            logger.exception("job %s failed", job.__name__)


async def run_scheduler() -> None:
    """In-process scheduler for JOBS_MODE=inline. Runs until cancelled (API shutdown)."""
    log(logger, "inline scheduler started", jobs=[j.__name__ for j, _ in PERIODIC] + [j.__name__ for j, *_ in DAILY])
    await asyncio.gather(*[_every(job, s) for job, s in PERIODIC], *[_daily(job, h, m) for job, h, m in DAILY])
