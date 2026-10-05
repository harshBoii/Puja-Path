import uuid

from fastapi import Cookie, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models import StaffRole, StaffUser, User
from security import DEVOTEE_COOKIE, STAFF_COOKIE, read_token
from services.i18n import LOCALES


async def optional_user(
    db: AsyncSession = Depends(get_db), pp_session: str | None = Cookie(default=None, alias=DEVOTEE_COOKIE)
) -> User | None:
    if not pp_session:
        return None
    data = read_token(pp_session, "devotee")
    if not data:
        return None
    user = await db.get(User, uuid.UUID(data["sub"]))
    if user is None or user.deleted_at is not None:
        return None
    return user


async def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "login_required")
    return user


async def current_staff(
    db: AsyncSession = Depends(get_db), pp_staff: str | None = Cookie(default=None, alias=STAFF_COOKIE)
) -> StaffUser:
    data = read_token(pp_staff or "", "staff")
    if not data or not data.get("mfa"):
        raise HTTPException(401, "staff_login_required")
    staff = await db.get(StaffUser, int(data["sub"]))
    if staff is None or not staff.active:
        raise HTTPException(401, "staff_login_required")
    return staff


def require_role(*roles: StaffRole):
    allowed = {StaffRole.admin, *roles}

    async def dep(staff: StaffUser = Depends(current_staff)) -> StaffUser:
        if staff.role not in allowed:
            raise HTTPException(403, "forbidden")
        return staff

    return dep


def locale_param(locale: str) -> str:
    if locale not in LOCALES:
        raise HTTPException(404, "unknown_locale")
    return locale


def currency_param(currency: str = Query("INR")) -> str:
    return "USD" if currency.upper() == "USD" else "INR"
