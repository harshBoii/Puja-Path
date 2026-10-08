import json
import uuid

from providers.errors import WebhookVerificationError
from providers.messaging.base import MessagingEvent, ProviderTemplate, SendResult, TemplateRef
from providers.recorder import record

# Numbers ending in these digits simulate provider behaviour in tests and local dev.
FAIL_INVALID_SUFFIX = "0000001"
FAIL_TIMEOUT_SUFFIX = "0000002"


class FakeMessagingProvider:
    name = "fake"

    def __init__(self, webhook_token: str = "fake-token"):
        self.webhook_token = webhook_token

    async def send_template(self, to, template: TemplateRef, params, header_media_url=None,
                            button_params=None, idempotency_key=""):
        from providers.errors import RetryableProviderError

        if to.endswith(FAIL_TIMEOUT_SUFFIX):
            raise RetryableProviderError("simulated timeout")
        payload = {
            "to": to, "template": template.key, "locale": template.locale, "ref": template.provider_ref,
            "params": params, "header_media_url": header_media_url, "button_params": button_params,
            "idempotency_key": idempotency_key,
        }
        await record("messaging", "send_template", payload)
        if to.endswith(FAIL_INVALID_SUFFIX):
            return SendResult(provider_message_id=None, accepted=False, error="invalid_number")
        return SendResult(provider_message_id=f"fake-{uuid.uuid4().hex[:16]}", accepted=True)

    async def send_session_text(self, to, text):
        await record("messaging", "send_session_text", {"to": to, "text": text})
        return SendResult(provider_message_id=f"fake-{uuid.uuid4().hex[:16]}", accepted=True)

    def parse_webhook(self, headers, body):
        if headers.get("x-fake-token") != self.webhook_token:
            raise WebhookVerificationError("bad token")
        data = json.loads(body)
        events = data if isinstance(data, list) else [data]
        return [
            MessagingEvent(
                kind=e["kind"], provider_message_id=e.get("id"), from_e164=e.get("from"), text=e.get("text"),
                button_payload=e.get("button"), error_code=e.get("code"), raw=e,
            )
            for e in events
        ]

    async def list_templates(self):
        from services.messaging_templates import TEMPLATE_SPECS, template_name

        return [ProviderTemplate(provider_ref=template_name(k), name=template_name(k), locale=None, status="approved",
                                 category=v["category"]) for k, v in TEMPLATE_SPECS.items()]
