"""Fake adapters record every call to `fake_provider_calls` (PRD §3)."""

from db import SessionLocal
from models import FakeProviderCall


async def record(kind: str, method: str, payload: dict) -> int:
    async with SessionLocal() as db:
        row = FakeProviderCall(kind=kind, method=method, payload=payload)
        db.add(row)
        await db.commit()
        return row.id
