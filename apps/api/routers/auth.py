"""Devotee login: phone + OTP over WhatsApp, SMS fallback after 30 s (PRD §5.8). 5 OTPs/hour/number."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from deps import optional_user
from models import OtpCode, User, WishlistItem
from providers.sms import send_sms_otp
from security import DEVOTEE_COOKIE, DEVOTEE_SESSION_DAYS, hash_otp, make_token
from services import notify
from services.i18n import LOCALES, utcnow

router = APIRouter(prefix="/v1/auth", tags=["auth"])
OTP_TTL = timedelta(minutes=10)
SMS_AFTER = timedelta(seconds=30)
RATE_PER_HOUR = 5


class OtpRequest(BaseModel):
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    channel: str = Field(default="whatsapp", pattern="^(whatsapp|sms)$")
    locale: str = "en"


@router.post("/otp/request")
async def request_otp(body: OtpRequest, db: AsyncSession = Depends(get_db)):
    now = utcnow()
    recent = (await db.execute(select(func.count()).select_from(OtpCode).where(
        OtpCode.phone_e164 == body.phone_e164, OtpCode.created_at > now - timedelta(hours=1)))).scalar()
    if recent >= RATE_PER_HOUR:
        raise HTTPException(429, "otp_rate_limited")
    if body.channel == "sms":
        last = (await db.execute(select(OtpCode).where(OtpCode.phone_e164 == body.phone_e164)
                                 .order_by(OtpCode.created_at.desc()).limit(1))).scalar_one_or_none()
        if last and now - last.created_at < SMS_AFTER:
            raise HTTPException(425, "sms_fallback_too_early")
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(OtpCode(phone_e164=body.phone_e164, code_hash=hash_otp(body.phone_e164, code), channel=body.channel,
                   expires_at=now + OTP_TTL))
    locale = body.locale if body.locale in LOCALES else "en"
    if body.channel == "whatsapp":
        # OTPs bypass quiet hours; occurrence key keeps each code a distinct message.
        await notify.queue(db, template_key="otp_login", to=body.phone_e164, locale=locale, params=[code],
                           button_params=[code], occurrence_key=f"otp:{secrets.token_hex(6)}")
        await notify.commit_and_dispatch(db)
    else:
        await db.commit()
        await send_sms_otp(body.phone_e164, code, locale)
    out = {"sent": True, "channel": body.channel, "sms_fallback_after_seconds": int(SMS_AFTER.total_seconds())}
    if settings.app_env == "test" or (settings.is_dev and settings.messaging_provider == "fake"):
        out["dev_code"] = code  # never in staging/production: lets local dev and tests log in
    return out


class OtpVerify(BaseModel):
    phone_e164: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    code: str = Field(pattern=r"^\d{6}$")
    locale: str = "en"
    wishlist: list[int] = Field(default_factory=list, max_length=200)


@router.post("/otp/verify")
async def verify_otp(body: OtpVerify, response: Response, db: AsyncSession = Depends(get_db)):
    now = utcnow()
    otp = (await db.execute(select(OtpCode).where(
        OtpCode.phone_e164 == body.phone_e164, OtpCode.used_at.is_(None), OtpCode.expires_at > now,
    ).order_by(OtpCode.created_at.desc()).limit(1).with_for_update())).scalar_one_or_none()
    if otp is None:
        raise HTTPException(400, "otp_invalid")
    otp.attempts += 1
    if otp.attempts > 5:
        otp.used_at = now
        await db.commit()
        raise HTTPException(400, "otp_invalid")
    if not secrets.compare_digest(otp.code_hash, hash_otp(body.phone_e164, body.code)):
        await db.commit()
        raise HTTPException(400, "otp_invalid")
    otp.used_at = now
    user = (await db.execute(select(User).where(User.phone_e164 == body.phone_e164))).scalar_one_or_none()
    if user is None:
        user = User(phone_e164=body.phone_e164, locale=body.locale if body.locale in LOCALES else "en")
        db.add(user)
        await db.flush()
    elif user.deleted_at is not None:
        raise HTTPException(403, "account_deleted")
    # Wishlist kept in local storage while logged out syncs on login.
    from sqlalchemy.dialects.postgresql import insert

    for pid in set(body.wishlist):
        await db.execute(insert(WishlistItem).values(user_id=user.id, puja_id=pid).on_conflict_do_nothing())
    await db.commit()
    token = make_token(str(user.id), "devotee", timedelta(days=DEVOTEE_SESSION_DAYS))
    response.set_cookie(DEVOTEE_COOKIE, token, max_age=DEVOTEE_SESSION_DAYS * 86400, httponly=True,
                        secure=not settings.is_dev, samesite="lax", path="/")
    return {"user": user_dict(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(DEVOTEE_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: User | None = Depends(optional_user)):
    return {"user": user_dict(user) if user else None}


def user_dict(u: User) -> dict:
    return {"id": str(u.id), "phone_e164": u.phone_e164, "name": u.name, "email": u.email, "locale": u.locale,
            "marketing_opt_in": u.marketing_opt_in_at is not None,
            "deletion_requested_at": u.deletion_requested_at.isoformat() if u.deletion_requested_at else None}
