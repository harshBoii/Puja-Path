"""Reviews come only from bookings (feedback_request quick replies); moderation before display."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Booking, Review, ReviewStatus
from services.i18n import utcnow


async def record_rating(db: AsyncSession, b: Booking, rating: int) -> None:
    r = (await db.execute(select(Review).where(Review.booking_id == b.id))).scalar_one_or_none()
    if r is None:
        db.add(Review(booking_id=b.id, rating=rating, locale=b.locale, status=ReviewStatus.pending))
    elif r.status == ReviewStatus.pending:
        r.rating = rating


async def maybe_attach_text(db: AsyncSession, b: Booking, text: str) -> None:
    """The optional text after a rating: the next free-text reply within a day."""
    r = (await db.execute(select(Review).where(Review.booking_id == b.id))).scalar_one_or_none()
    if r and not r.text and r.status == ReviewStatus.pending and r.created_at > utcnow() - timedelta(days=1):
        r.text = text[:1000]
