"""WATI adapter — https://docs.wati.io/reference/sendtemplatemessage"""

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

_STATUS_EVENTS = {
    "templateMessageSent_v2": "sent",
    "templateMessageSent": "sent",
    "sentMessageDELIVERED_v2": "delivered",
    "sentMessageDELIVERED": "delivered",
    "sentMessageREAD_v2": "read",
    "sentMessageREAD": "read",
    "templateMessageFailed": "failed",
}


class WatiProvider:
    name = "wati"

    def __init__(self, endpoint: str, token: str, webhook_token: str):
        self.endpoint = endpoint.rstrip("/")
        self.token = token if token.lower().startswith("bearer ") else f"Bearer {token}"
        self.webhook_token = webhook_token

    @property
    def _headers(self) -> dict:
        return {"Authorization": self.token, "Content-Type": "application/json"}

    async def send_template(self, to, template: TemplateRef, params, header_media_url=None,
                            button_params=None, idempotency_key=""):
        names = template.variables or [str(i + 1) for i in range(len(params))]
        parameters = [{"name": n, "value": v} for n, v in zip(names, params, strict=False)]
        if header_media_url:
            parameters.append({"name": "media_url", "value": header_media_url})
        for i, value in enumerate(button_params or []):
            # WATI names a dynamic URL button's variable by its position ({{1}} -> "1").
            parameters.append({"name": str(i + 1), "value": value})
        body = {
            "template_name": template.provider_ref,
            # broadcast_name groups sends in WATI's dashboard; idempotency key keeps it unique per message.
            "broadcast_name": (idempotency_key or template.key)[:60],
            "parameters": parameters,
        }
        resp = await request(
            "POST", f"{self.endpoint}/api/v2/sendTemplateMessage", params={"whatsappNumber": digits(to)},
            headers=self._headers, json=body,
        )
        data = resp.json()
        if not data.get("result", False):
            return SendResult(None, False, error=str(data.get("info") or data.get("error") or "rejected"))
        return SendResult(provider_message_id=data.get("localMessageId") or data.get("id"), accepted=True)

    async def send_session_text(self, to, text):
        resp = await request(
            "POST", f"{self.endpoint}/api/v1/sendSessionMessage/{digits(to)}",
            params={"messageText": text}, headers=self._headers,
        )
        data = resp.json()
        return SendResult(data.get("message", {}).get("id") if isinstance(data.get("message"), dict) else None,
                          bool(data.get("result", True)))

    def parse_webhook(self, headers, body):
        token = headers.get("x-webhook-token", "")
        if not self.webhook_token or not hmac.compare_digest(token, self.webhook_token):
            raise WebhookVerificationError("WATI webhook token mismatch")
        data = json.loads(body)
        items = data if isinstance(data, list) else [data]
        events: list[MessagingEvent] = []
        for d in items:
            et = d.get("eventType", "")
            if et in _STATUS_EVENTS:
                events.append(MessagingEvent(
                    kind=_STATUS_EVENTS[et],  # type: ignore[arg-type]
                    provider_message_id=d.get("localMessageId") or d.get("id"),
                    error_code=str(d.get("failedCode") or d.get("errorCode") or "") or None,
                    raw=d,
                ))
            elif et == "messageReceived":
                phone = "+" + str(d.get("waId", "")).lstrip("+")
                reply = d.get("buttonReply") or d.get("interactiveButtonReply") or {}
                if reply or d.get("type") in ("button", "interactive"):
                    events.append(MessagingEvent(kind="inbound_button", from_e164=phone,
                                                 button_payload=reply.get("payload") or reply.get("text") or d.get("text"),
                                                 text=d.get("text"), raw=d))
                else:
                    events.append(MessagingEvent(kind="inbound_text", from_e164=phone, text=d.get("text"), raw=d))
        return events

    async def list_templates(self):
        resp = await request("GET", f"{self.endpoint}/api/v1/getMessageTemplates", headers=self._headers,
                             params={"pageSize": 500})
        out = []
        for t in resp.json().get("messageTemplates", []):
            lang = t.get("language")
            out.append(ProviderTemplate(
                provider_ref=t.get("elementName", ""), name=t.get("elementName", ""),
                locale=(lang.get("value") if isinstance(lang, dict) else lang),
                status=str(t.get("status", "")).lower(), category=t.get("category"),
            ))
        return out
