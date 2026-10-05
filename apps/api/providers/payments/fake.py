"""Fake gateway. Payments are completed by a signed webhook, exactly like a real gateway.

In local dev the storefront's fake checkout calls /v1/dev/fake-gateway/... which signs and delivers that webhook.
"""

import hashlib
import hmac
import json
import uuid

from providers.errors import WebhookVerificationError
from providers.payments.base import ChargeRef, MandateRef, OrderRef, PaymentEvent, RefundRef
from providers.recorder import record


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class FakePaymentProvider:
    name = "fake"

    def __init__(self, webhook_secret: str):
        self.webhook_secret = webhook_secret

    async def create_order(self, booking_id, amount_minor, currency, customer, notes):
        order_id = f"fake_order_{uuid.uuid4().hex[:14]}"
        await record("payments", "create_order", {"booking_id": booking_id, "order_id": order_id,
                                                  "amount_minor": amount_minor, "currency": currency, "notes": notes})
        return OrderRef("fake", order_id, amount_minor, currency, checkout={"mode": "fake", "order_id": order_id})

    async def create_mandate(self, subscription_id, max_amount_minor, frequency, start_at, end_at, customer):
        mandate_id = f"fake_mandate_{uuid.uuid4().hex[:12]}"
        await record("payments", "create_mandate", {"subscription_id": subscription_id, "mandate_id": mandate_id,
                                                    "max_amount_minor": max_amount_minor, "frequency": frequency,
                                                    "start_at": start_at.isoformat(), "end_at": end_at.isoformat()})
        return MandateRef("fake", mandate_id, token=None, status="created")

    async def charge_mandate(self, mandate_token, amount_minor, idempotency_key):
        order_id = f"fake_order_{uuid.uuid4().hex[:14]}"
        await record("payments", "charge_mandate", {"token": mandate_token, "amount_minor": amount_minor,
                                                    "idempotency_key": idempotency_key, "order_id": order_id})
        return ChargeRef("fake", order_id=order_id, payment_id=None, status="created")

    async def cancel_mandate(self, mandate_token):
        await record("payments", "cancel_mandate", {"token": mandate_token})

    async def refund(self, payment_id, amount_minor, reason, idempotency_key):
        refund_id = f"fake_rfnd_{uuid.uuid4().hex[:12]}"
        await record("payments", "refund", {"payment_id": payment_id, "amount_minor": amount_minor,
                                            "reason": reason, "idempotency_key": idempotency_key,
                                            "refund_id": refund_id})
        return RefundRef("fake", refund_id, "requested")

    def verify_webhook(self, headers, body):
        sig = headers.get("x-fake-signature", "")
        if not hmac.compare_digest(sig, sign(self.webhook_secret, body)):
            raise WebhookVerificationError("bad signature")
        d = json.loads(body)
        return [PaymentEvent(
            kind=d["kind"], event_id=d["event_id"], order_id=d.get("order_id"), payment_id=d.get("payment_id"),
            amount_minor=d.get("amount_minor"), currency=d.get("currency"), refund_id=d.get("refund_id"),
            mandate_token=d.get("mandate_token"), mandate_ref=d.get("mandate_ref"), notes=d.get("notes") or {},
            error=d.get("error"), raw=d,
        )]

    def build_webhook(self, **event) -> tuple[dict, bytes]:
        event.setdefault("event_id", f"fake_evt_{uuid.uuid4().hex}")
        body = json.dumps(event).encode()
        return {"x-fake-signature": sign(self.webhook_secret, body)}, body
