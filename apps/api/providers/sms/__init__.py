"""SMS OTP fallback (PRD §5.8). `fake` records; `msg91` uses the MSG91 OTP API; `telnyx` the Telnyx Messaging API."""

from config import settings
from providers.messaging.http import request
from providers.recorder import record


def otp_text(code: str, locale: str) -> str:
    from services.messaging_templates import render_body

    return f"{settings.brand}: {render_body('otp_login', locale, [code])}"


async def send_sms_otp(phone_e164: str, code: str, locale: str = "en") -> None:
    if settings.sms_otp_provider == "telnyx":
        body = {"from": settings.sms_otp_from, "to": phone_e164, "text": otp_text(code, locale)}
        if settings.sms_otp_messaging_profile_id:
            body["messaging_profile_id"] = settings.sms_otp_messaging_profile_id
        await request("POST", "https://api.telnyx.com/v2/messages",
                      headers={"Authorization": f"Bearer {settings.sms_otp_api_key}"}, json=body)
        return
    if settings.sms_otp_provider == "msg91":
        await request("POST", "https://control.msg91.com/api/v5/otp",
                      headers={"authkey": settings.sms_otp_api_key},
                      params={"mobile": phone_e164.lstrip("+"), "otp": code})
        return
    await record("sms", "send_otp", {"to": phone_e164, "code": code})
