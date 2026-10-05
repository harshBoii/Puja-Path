"""SMS OTP fallback (PRD §5.8). `fake` records; `msg91` uses the MSG91 OTP API."""

from config import settings
from providers.messaging.http import request
from providers.recorder import record


async def send_sms_otp(phone_e164: str, code: str) -> None:
    if settings.sms_otp_provider == "msg91":
        await request("POST", "https://control.msg91.com/api/v5/otp",
                      headers={"authkey": settings.sms_otp_api_key},
                      params={"mobile": phone_e164.lstrip("+"), "otp": code})
        return
    await record("sms", "send_otp", {"to": phone_e164, "code": code})
