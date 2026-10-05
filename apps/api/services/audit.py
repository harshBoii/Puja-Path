from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog


async def audit(db: AsyncSession, actor_staff_id: int | None, action: str, entity: str, entity_id, diff=None) -> None:
    db.add(AuditLog(actor_staff_id=actor_staff_id, action=action, entity=entity, entity_id=str(entity_id),
                    diff=_jsonable(diff)))


def _jsonable(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]
    if hasattr(v, "value"):
        return v.value
    return str(v)
