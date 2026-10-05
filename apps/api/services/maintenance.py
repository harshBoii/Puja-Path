"""Daily jobs: settlement reconciliation and config-driven data purges (PRD §8, §12 DPDP)."""

import logging
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from logging_setup import log
from models import Booking, BookingName, FamilyMember, Payment, ProofClip, ReconciliationItem, Shipment, User
from services import site_config
from services.alerts import ops_alert
from services.i18n import IST, utcnow

logger = logging.getLogger("maintenance")


async def reconcile(db: AsyncSession, settlements: list[dict] | None = None, provider: str = "fake") -> int:
    """Matches gateway settlements to captured payments and flags mismatches for the finance view.

    `settlements` is [{payment_id, amount_minor}] pulled from the gateway's settlement report. With the fake
    gateway every captured payment settles at its own amount, so only internal inconsistencies show up.
    """
    today = utcnow().astimezone(IST).date()
    captured = {p.provider_payment_id: p for p in (await db.execute(
        select(Payment).where(Payment.status == "captured", Payment.settled_at.is_(None),
                              Payment.created_at < utcnow() - timedelta(days=1))
    )).scalars() if p.provider_payment_id}
    if settlements is None:
        settlements = [{"payment_id": pid, "amount_minor": p.amount_minor} for pid, p in captured.items()]
    flagged = 0
    for s in settlements:
        p = captured.pop(s["payment_id"], None)
        if p is None:
            db.add(ReconciliationItem(run_date=today, provider=provider, provider_payment_id=s["payment_id"],
                                      kind="missing_in_db", detail=s))
            flagged += 1
        elif p.amount_minor != s["amount_minor"]:
            db.add(ReconciliationItem(run_date=today, provider=provider, provider_payment_id=s["payment_id"],
                                      payment_id=p.id, kind="amount_mismatch",
                                      detail={"expected": p.amount_minor, "settled": s["amount_minor"]}))
            flagged += 1
        else:
            p.settled_at = utcnow()
    for pid, p in captured.items():
        if p.created_at < utcnow() - timedelta(days=4):
            db.add(ReconciliationItem(run_date=today, provider=provider, provider_payment_id=pid, payment_id=p.id,
                                      kind="not_settled", detail={"amount": p.amount_minor}))
            flagged += 1
    if flagged:
        await ops_alert("Reconciliation mismatches", f"{flagged} items flagged on {today}")
    return flagged


async def purge(db: AsyncSession) -> dict:
    """Account deletion (30 days) + retention purges driven by site_config.retention."""
    now = utcnow()
    stats = {"accounts": 0, "names": 0, "clips": 0}
    due = (await db.execute(select(User).where(User.deletion_requested_at.is_not(None), User.deleted_at.is_(None),
                                               User.deletion_requested_at < now - timedelta(days=29)))).scalars()
    for u in due:
        # Invoices (bookings + payments) are kept as the law requires; personal fields are anonymised.
        await db.execute(update(BookingName).where(BookingName.booking_id.in_(
            select(Booking.id).where(Booking.user_id == u.id))).values(name="(deleted)", gotra=None, nakshatra=None,
                                                                       relation=None))
        await db.execute(update(Booking).where(Booking.user_id == u.id).values(wish=None))
        await db.execute(update(Shipment).where(Shipment.booking_id.in_(
            select(Booking.id).where(Booking.user_id == u.id))).values(address={"anonymised": True}))
        await db.execute(FamilyMember.__table__.delete().where(FamilyMember.user_id == u.id))
        u.name, u.email, u.marketing_opt_in_at, u.deleted_at = None, None, None, now
        u.phone_e164 = f"deleted:{u.id.hex[:12]}"
        stats["accounts"] += 1
    retention = await site_config.get(db, "retention") or {}
    if retention.get("sankalp_names_days"):
        cutoff = now - timedelta(days=int(retention["sankalp_names_days"]))
        res = await db.execute(update(BookingName).where(BookingName.booking_id.in_(
            select(Booking.id).where(Booking.completed_at < cutoff))).values(name="(purged)", gotra=None,
                                                                            nakshatra=None))
        stats["names"] = res.rowcount or 0
    if retention.get("proof_video_days"):
        cutoff = now - timedelta(days=int(retention["proof_video_days"]))
        res = await db.execute(update(ProofClip).where(ProofClip.booking_id.in_(
            select(Booking.id).where(Booking.proof_sent_at < cutoff))).values(r2_key=None, thumb_key=None))
        stats["clips"] = res.rowcount or 0
    log(logger, "purge done", **stats)
    return stats
