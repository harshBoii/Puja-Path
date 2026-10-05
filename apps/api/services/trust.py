"""Trust bar: live database counts, rounded down, with an as-of date, hidden below thresholds (PRD §12)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Booking, BookingStatus, Review, ReviewStatus
from services import site_config
from services.i18n import utcnow

DONE = [BookingStatus.proof_sent, BookingStatus.completed]


def round_down(n: int) -> int:
    if n < 100:
        return n
    step = 10 ** (len(str(n)) - 2)  # keep two significant digits
    return n // step * step


async def trust_bar(db: AsyncSession) -> dict:
    thresholds = await site_config.get(db, "trust_bar_thresholds")
    pujas = (await db.execute(select(func.count()).select_from(Booking).where(Booking.status.in_(DONE)))).scalar()
    devotees = (await db.execute(select(func.count(func.distinct(Booking.user_id)))
                                 .where(Booking.status.in_(DONE)))).scalar()
    avg, count = (await db.execute(select(func.avg(Review.rating), func.count())
                                   .where(Review.status == ReviewStatus.approved))).one()
    items = []
    if pujas >= thresholds["pujas_completed"]:
        items.append({"key": "pujas_completed", "value": round_down(pujas)})
    if devotees >= thresholds["devotees"]:
        items.append({"key": "devotees", "value": round_down(devotees)})
    if count >= thresholds["reviews"]:
        items.append({"key": "rating", "value": float(int(avg * 10) / 10), "count": count})
    return {"items": items, "as_of": utcnow().date().isoformat()}
