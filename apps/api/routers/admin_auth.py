"""Staff sign-in: email + password + TOTP; 12-hour sessions; first login enrols the authenticator (PRD §10)."""

from datetime import timedelta

import pyotp
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from deps import current_staff, require_role
from models import StaffRole, StaffUser
from security import STAFF_COOKIE, STAFF_SESSION_HOURS, check_password, hash_password, make_token, read_token
from services.audit import audit

router = APIRouter(prefix="/v1/admin/auth", tags=["admin"])
staff_router = APIRouter(prefix="/v1/admin/staff", tags=["admin"])
PENDING_COOKIE = "pp_staff_pending"


def _cookie(response: Response, name: str, token: str, seconds: int) -> None:
    response.set_cookie(name, token, max_age=seconds, httponly=True, secure=not settings.is_dev, samesite="strict",
                        path="/")


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    staff = (await db.execute(select(StaffUser).where(StaffUser.email == body.email.lower().strip()))
             ).scalar_one_or_none()
    if staff is None or not staff.active or not check_password(body.password, staff.password_hash):
        raise HTTPException(401, "invalid_credentials")
    token = make_token(str(staff.id), "staff_pending", timedelta(minutes=10))
    _cookie(response, PENDING_COOKIE, token, 600)
    if not staff.totp_confirmed:
        if not staff.totp_secret:
            staff.totp_secret = pyotp.random_base32()
            await db.commit()
        uri = pyotp.TOTP(staff.totp_secret).provisioning_uri(name=staff.email, issuer_name=settings.brand)
        return {"step": "enroll_totp", "otpauth_uri": uri, "secret": staff.totp_secret}
    return {"step": "totp"}


class TotpIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/totp")
async def verify_totp(body: TotpIn, response: Response, db: AsyncSession = Depends(get_db),
                      pending: str | None = Cookie(default=None, alias=PENDING_COOKIE)):
    data = read_token(pending or "", "staff_pending")
    if not data:
        raise HTTPException(401, "login_expired")
    staff = await db.get(StaffUser, int(data["sub"]))
    if staff is None or not staff.totp_secret or not pyotp.TOTP(staff.totp_secret).verify(body.code, valid_window=1):
        raise HTTPException(401, "invalid_code")
    staff.totp_confirmed = True
    await audit(db, staff.id, "staff.login", "staff_user", staff.id)
    await db.commit()
    token = make_token(str(staff.id), "staff", timedelta(hours=STAFF_SESSION_HOURS), mfa=True, role=staff.role.value)
    _cookie(response, STAFF_COOKIE, token, STAFF_SESSION_HOURS * 3600)
    response.delete_cookie(PENDING_COOKIE, path="/")
    return {"staff": staff_dict(staff)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(STAFF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
async def me(staff: StaffUser = Depends(current_staff)):
    return {"staff": staff_dict(staff)}


def staff_dict(s: StaffUser) -> dict:
    return {"id": s.id, "email": s.email, "name": s.name, "role": s.role.value, "active": s.active,
            "totp_enrolled": s.totp_confirmed}


class StaffIn(BaseModel):
    email: str
    name: str
    role: StaffRole
    password: str = Field(min_length=10)


class StaffPatch(BaseModel):
    name: str | None = None
    role: StaffRole | None = None
    active: bool | None = None
    reset_totp: bool = False
    password: str | None = Field(default=None, min_length=10)


@staff_router.get("")
async def list_staff(db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(require_role())):
    return [staff_dict(s) for s in (await db.execute(select(StaffUser).order_by(StaffUser.id))).scalars()]


@staff_router.post("", status_code=201)
async def create_staff(body: StaffIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(require_role())):
    s = StaffUser(email=body.email.lower().strip(), name=body.name, role=body.role,
                  password_hash=hash_password(body.password), active=True)
    db.add(s)
    await db.flush()
    await audit(db, staff.id, "staff.create", "staff_user", s.id, {"email": s.email, "role": s.role})
    await db.commit()
    return staff_dict(s)


@staff_router.patch("/{staff_id}")
async def update_staff(staff_id: int, body: StaffPatch, db: AsyncSession = Depends(get_db),
                       staff: StaffUser = Depends(require_role())):
    s = await db.get(StaffUser, staff_id)
    if s is None:
        raise HTTPException(404, "not_found")
    diff = body.model_dump(exclude_none=True, exclude={"password"})
    if body.name is not None:
        s.name = body.name
    if body.role is not None:
        s.role = body.role
    if body.active is not None:
        s.active = body.active
    if body.reset_totp:
        s.totp_secret, s.totp_confirmed = None, False
    if body.password:
        s.password_hash = hash_password(body.password)
        diff["password"] = "changed"
    await audit(db, staff.id, "staff.update", "staff_user", s.id, diff)
    await db.commit()
    return staff_dict(s)
