"""Arq worker: message sends, scheduled sweeps, clipping, webhooks retries.

Run: cd apps/api && uv run arq --custom-log-dict logging_setup.ARQ_LOG ../worker/worker.WorkerSettings
(or `uv run python ../worker/worker.py`).
"""

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(API_DIR))

from arq import cron  # noqa: E402

from db import SessionLocal  # noqa: E402
from logging_setup import setup_logging  # noqa: E402
from services import bookings as booking_svc  # noqa: E402
from services import events as event_svc  # noqa: E402
from services import maintenance, notify, seva, sla  # noqa: E402
from services import proof as proof_svc  # noqa: E402
from services.jobs import enqueue, redis_settings  # noqa: E402
from services.revalidate import puja_tags, revalidate  # noqa: E402

setup_logging()


async def send_message(ctx, message_id: str) -> str:
    return await notify.send_one(message_id)


async def dispatch_due(ctx) -> int:
    """Every 15 s: picks up scheduled, held (quiet hours) and retrying messages."""
    async with SessionLocal() as db:
        ids = await notify.due_message_ids(db)
    for mid in ids:
        await enqueue("send_message", mid, _job_id=f"msg:{mid}:{int(__import__('time').time() // 15)}")
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
    from datetime import timedelta

    from sqlalchemy import select

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


class WorkerSettings:
    redis_settings = redis_settings()
    functions = [send_message, cut_clips, fake_payment_webhook]
    cron_jobs = [
        cron(dispatch_due, second={0, 15, 30, 45}, run_at_startup=True),
        cron(lock_events, second={5, 35}),
        cron(expire_payments, minute=set(range(0, 60, 2)), second=10),
        cron(reschedule_defaults, minute=set(range(0, 60, 10)), second=20),
        cron(sla_check, minute=set(range(0, 60, 10)), second=25),
        cron(autopay, minute=set(range(0, 60, 5)), second=40),
        cron(checkout_reminders, minute=set(range(0, 60, 10)), second=50),
        cron(daily_reconcile, hour=1, minute=30),  # UTC ≈ 07:00 IST
        cron(daily_purge, hour=21, minute=0),
    ]
    max_jobs = 20
    job_timeout = 1800
    keep_result = 60


if __name__ == "__main__":
    from arq import run_worker

    run_worker(WorkerSettings)
