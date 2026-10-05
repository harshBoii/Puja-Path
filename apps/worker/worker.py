"""Arq worker for JOBS_MODE=worker (Redis). Not needed with JOBS_MODE=inline, where the API runs the same jobs itself.

Run: cd apps/api && uv run python ../worker/worker.py
"""

import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(API_DIR))

from arq import cron  # noqa: E402

from config import settings  # noqa: E402
from logging_setup import setup_logging  # noqa: E402
from services.jobs import redis_settings  # noqa: E402
from services.tasks import DAILY, ONE_OFF, PERIODIC  # noqa: E402

setup_logging()


def _cron_for(job, seconds: int):
    """Turns "every N seconds" into an Arq cron spec with the same cadence."""
    if seconds < 60:
        return cron(job, second=set(range(0, 60, seconds)), run_at_startup=job.__name__ == "dispatch_due")
    return cron(job, minute=set(range(0, 60, seconds // 60)), second=0)


class WorkerSettings:
    redis_settings = redis_settings()
    functions = list(ONE_OFF.values())
    cron_jobs = [_cron_for(job, s) for job, s in PERIODIC] + [cron(job, hour=h, minute=m) for job, h, m in DAILY]
    max_jobs = 20
    job_timeout = 1800
    keep_result = 60


if __name__ == "__main__":
    if settings.jobs_mode != "worker":
        print(f"JOBS_MODE={settings.jobs_mode}: the API runs background jobs itself; this worker is not needed.")
        sys.exit(0)
    from arq import run_worker

    run_worker(WorkerSettings)
