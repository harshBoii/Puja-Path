"""Gupshup adapter — https://docs.gupshup.io/docs/template-messages

Event payload shapes follow Gupshup's v2 callback format; confirm against the app dashboard before launch.
"""

import hmac
import json

from providers.errors import WebhookVerificationError
from providers.messaging.base import (
    MessagingEvent,
    ProviderTemplate,
    SendResult,
    TemplateRef,
    digits,
)
from providers.messaging.http import request

API = "https://api.gupshup.io"
_STATUS = {"enqueued": None, "sent": "sent", "delivered": "delivered", "read": "read", "failed": "failed"}


class GupshupProvider:
    name = "gupshup"

    def __init__(self, api_key: str, app_name: str, source_number: str, webhook_token: str):
        self.api_key = api_key
        self.app_name = app_name
        self.source = digits(source_number)
        self.webhook_token = webhook_token

    async def send_template(self, to, template: TemplateRef, params, header_media_url=None,
                            button_params=None, idempotency_key=""):
        form = {
            "source": self.source,
            "src.name": self.app_name,
            "destination": digits(to),
            "template": json.dumps({"id": template.provider_ref, "params": list(params) + list(button_params or [])}),
        }
        if header_media_url:
            kind = "video" if header_media_url.split("?")[0].endswith(".mp4") else "image"
            form["message"] = json.dumps({"type": kind, kind: {"link": header_media_url}})
        resp = await request("POST", f"{API}/wa/api/v1/template/msg", headers={"apikey": self.api_key}, data=form)
        data = resp.json()
        if data.get("status") not in ("submitted", "success"):
            return SendResult(None, False, error=str(data.get("message") or data))
        return SendResult(provider_message_id=data.get("messageId"), accepted=True)

    async def send_session_text(self, to, text):
        form = {
            "channel": "whatsapp", "source": self.source, "src.name": self.app_name,
            "destination": digits(to), "message": json.dumps({"type": "text", "text": text}),
        }
        resp = await request("POST", f"{API}/wa/api/v1/msg", headers={"apikey": self.api_key}, data=form)
        data = resp.json()
        return SendResult(data.get("messageId"), data.get("status") == "submitted")

    def parse_webhook(self, headers, body):
        token = headers.get("x-webhook-token", "")
        if not self.webhook_token or not hmac.compare_digest(token, self.webhook_token):
            raise WebhookVerificationError("Gupshup webhook token mismatch")
        data = json.loads(body)
        items = data if isinstance(data, list) else [data]
        events: list[MessagingEvent] = []
        for d in items:
            payload = d.get("payload", {}) or {}
            if d.get("type") == "message-event":
                kind = _STATUS.get(payload.get("type", ""))
                if not kind:
                    continue
                inner = payload.get("payload", {}) or {}
                events.append(MessagingEvent(
                    kind=kind,  # type: ignore[arg-type]
                    provider_message_id=payload.get("gsId") or payload.get("id"),
                    error_code=str(inner.get("code")) if kind == "failed" and inner.get("code") is not None else None,
                    raw=d,
                ))
            elif d.get("type") == "message":
                sender = payload.get("sender", {}) or {}
                phone = "+" + str(sender.get("phone") or payload.get("source", "")).lstrip("+")
                inner = payload.get("payload", {}) or {}
                if payload.get("type") in ("button_reply", "quick_reply"):
                    events.append(MessagingEvent(kind="inbound_button", from_e164=phone,
                                                 button_payload=inner.get("postbackText") or inner.get("title")
                                                 or inner.get("text"), text=inner.get("text"), raw=d))
                else:
                    events.append(MessagingEvent(kind="inbound_text", from_e164=phone, text=inner.get("text"), raw=d))
        return events

    async def list_templates(self):
        resp = await request("GET", f"{API}/sm/api/v1/template/list/{self.app_name}", headers={"apikey": self.api_key})
        return [
            ProviderTemplate(provider_ref=t.get("id", ""), name=t.get("elementName", ""),
                             locale=t.get("languageCode"), status=str(t.get("status", "")).lower(),
                             category=t.get("category"))
            for t in resp.json().get("templates", [])
        ]
