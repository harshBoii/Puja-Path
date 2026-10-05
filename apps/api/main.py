import asyncio
import contextlib
import hmac
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from config import settings
from logging_setup import setup_logging
from routers import (
    account,
    admin_auth,
    admin_bookings,
    admin_catalog,
    admin_misc,
    admin_ops,
    auth,
    checkout,
    public,
    webhooks,
)

setup_logging()
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.local_media_dir.mkdir(parents=True, exist_ok=True)
    scheduler = None
    if settings.jobs_mode == "inline":
        from services.tasks import run_scheduler

        scheduler = asyncio.create_task(run_scheduler())
    yield
    if scheduler:
        scheduler.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler


app = FastAPI(title=f"{settings.brand} API", version="1.0.0", lifespan=lifespan)

# Admin routers first: the public `/v1/{locale}/...` routes would otherwise capture `/v1/admin/...` paths.
for r in (admin_auth, admin_catalog, admin_ops, admin_bookings, admin_misc):
    app.include_router(r.router)
app.include_router(admin_auth.staff_router)
for r in (public, auth, checkout, account, webhooks):
    app.include_router(r.router)

if settings.is_dev:
    from routers import dev

    app.include_router(dev.router)

# Dev/CI media; production serves R2 through the CDN domain.
settings.local_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.local_media_dir), name="media")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "jobs_mode": settings.jobs_mode}


@app.post("/v1/internal/cron", include_in_schema=False)
async def cron_tick(x_cron_secret: str = Header(default="")):
    """Runs every periodic job once, for hosts where the API cannot keep a scheduler alive (e.g. serverless).
    Disabled unless CRON_SECRET is set."""
    if not settings.cron_secret or not hmac.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(404, "not_found")
    from services.tasks import run_all_once

    return await run_all_once()
