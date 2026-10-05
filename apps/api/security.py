import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from config import settings

DEVOTEE_COOKIE = "pp_session"
STAFF_COOKIE = "pp_staff"
DEVOTEE_SESSION_DAYS = 90
STAFF_SESSION_HOURS = 12

# No 0/O/1/I so codes read cleanly over the phone.
_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def booking_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


def proof_token() -> str:
    return secrets.token_urlsafe(16)  # 128-bit


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def hash_otp(phone: str, code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def make_token(sub: str, kind: str, ttl: timedelta, **claims) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": sub, "kind": kind, "iat": now, "exp": now + ttl, **claims}, settings.jwt_secret, algorithm="HS256"
    )


def read_token(token: str, kind: str) -> dict | None:
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data if data.get("kind") == kind else None
