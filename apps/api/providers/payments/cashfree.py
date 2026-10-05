"""Cashfree adapter — PG orders (API version 2023-08-01), subscriptions, refunds, webhooks.

Docs: https://docs.cashfree.com/reference/pg-new-apis-endpoint
`provider_payment_id` is stored as "{order_id}|{cf_payment_id}" because Cashfree refunds are keyed by order.
"""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from providers.errors import WebhookVerificationError
from providers.messaging.http import request
from providers.payments.base import ChargeRef, Customer, MandateRef, OrderRef, PaymentEvent, RefundRef

API_VERSION = "2023-08-01"


def _major(minor: int) -> float:
    return round(minor / 100, 2)


def _minor(major) -> int | None:
    return None if major is None else int(round(float(major) * 100))


class CashfreeProvider:
    name = "cashfree"

    def __init__(self, app_id: str, secret: str, webhook_secret: str, env: str = "sandbox"):
        self.app_id = app_id
        self.secret = secret
        self.webhook_secret = webhook_secret or secret
        self.env = env
        self.base = "https://api.cashfree.com/pg" if env == "production" else "https://sandbox.cashfree.com/pg"

    @property
    def _headers(self) -> dict:
        return {"x-client-id": self.app_id, "x-client-secret": self.secret, "x-api-version": API_VERSION}

    async def _post(self, path: str, body: dict, idem: str | None = None) -> dict:
        headers = dict(self._headers)
        if idem:
            headers["x-idempotency-key"] = idem
        return (await request("POST", f"{self.base}{path}", headers=headers, json=body)).json()

    async def create_order(self, booking_id, amount_minor, currency, customer: Customer, notes):
        order_id = f"pp_{booking_id.replace('-', '')[:30]}_{int(datetime.now(UTC).timestamp())}"
        data = await self._post("/orders", {
            "order_id": order_id, "order_amount": _major(amount_minor), "order_currency": currency,
            "customer_details": {"customer_id": customer.phone_e164.lstrip("+"), "customer_phone": customer.phone_e164,
                                 "customer_name": customer.name or "Devotee", "customer_email": customer.email},
            "order_tags": {k: str(v)[:250] for k, v in notes.items()},
        })
        return OrderRef("cashfree", order_id, amount_minor, currency, checkout={
            "mode": "cashfree", "payment_session_id": data["payment_session_id"], "order_id": order_id,
            "env": self.env,
        })

    async def create_mandate(self, subscription_id, max_amount_minor, frequency, start_at, end_at: datetime, customer):
        sub_id = f"pp_sub_{subscription_id.replace('-', '')[:24]}"
        data = await self._post("/subscriptions", {
            "subscription_id": sub_id,
            "customer_details": {"customer_phone": customer.phone_e164, "customer_name": customer.name or "Devotee",
                                 "customer_email": customer.email or "devotee@example.invalid"},
            "plan_details": {"plan_name": f"seva-{sub_id}", "plan_type": "ON_DEMAND",
                             "plan_max_amount": _major(max_amount_minor), "plan_currency": "INR"},
            "authorization_details": {"authorization_amount": _major(max_amount_minor),
                                      "authorization_amount_refund": False, "payment_methods": ["upi"]},
            "subscription_expiry_time": end_at.isoformat(),
        })
        first = OrderRef("cashfree", sub_id, max_amount_minor, "INR", checkout={
            "mode": "cashfree_subscription", "subscription_session_id": data.get("subscription_session_id"),
            "env": self.env,
        })
        return MandateRef("cashfree", mandate_id=sub_id, token=sub_id, status="created", first_order=first)

    async def charge_mandate(self, mandate_token, amount_minor, idempotency_key):
        data = await self._post("/subscriptions/pay", {
            "subscription_id": mandate_token, "payment_id": idempotency_key[:40],
            "payment_amount": _major(amount_minor), "payment_type": "CHARGE",
        }, idem=idempotency_key)
        return ChargeRef("cashfree", order_id=idempotency_key[:40], payment_id=data.get("cf_payment_id"),
                         status="created")

    async def cancel_mandate(self, mandate_token):
        await self._post(f"/subscriptions/{mandate_token}/manage",
                         {"subscription_id": mandate_token, "action": "CANCEL"})

    async def refund(self, payment_id, amount_minor, reason, idempotency_key):
        order_id = payment_id.split("|", 1)[0]
        data = await self._post(f"/orders/{order_id}/refunds", {
            "refund_amount": _major(amount_minor), "refund_id": idempotency_key[:40], "refund_note": reason[:100],
        }, idem=idempotency_key)
        return RefundRef("cashfree", str(data.get("refund_id") or idempotency_key[:40]), "requested")

    def verify_webhook(self, headers, body):
        ts = headers.get("x-webhook-timestamp", "")
        expected = base64.b64encode(
            hmac.new(self.webhook_secret.encode(), ts.encode() + body, hashlib.sha256).digest()
        ).decode()
        if not hmac.compare_digest(headers.get("x-webhook-signature", ""), expected):
            raise WebhookVerificationError("Cashfree signature mismatch")
        d = json.loads(body)
        t = d.get("type", "")
        data = d.get("data", {})
        order = data.get("order") or {}
        pay = data.get("payment") or {}
        event_id = headers.get("x-idempotency-key") or f"{t}:{order.get('order_id')}:{pay.get('cf_payment_id')}:{ts}"
        if t == "PAYMENT_SUCCESS_WEBHOOK":
            return [PaymentEvent("payment_captured", event_id, order_id=order.get("order_id"),
                                 payment_id=f"{order.get('order_id')}|{pay.get('cf_payment_id')}",
                                 amount_minor=_minor(pay.get("payment_amount")),
                                 currency=pay.get("payment_currency"), notes=order.get("order_tags") or {}, raw=d)]
        if t in ("PAYMENT_FAILED_WEBHOOK", "PAYMENT_USER_DROPPED_WEBHOOK"):
            return [PaymentEvent("payment_failed", event_id, order_id=order.get("order_id"),
                                 error=pay.get("payment_message"), raw=d)]
        if t == "REFUND_STATUS_WEBHOOK":
            r = data.get("refund") or {}
            ok = r.get("refund_status") == "SUCCESS"
            return [PaymentEvent("refund_processed" if ok else "refund_failed", event_id,
                                 payment_id=r.get("order_id"), refund_id=str(r.get("refund_id")),
                                 amount_minor=_minor(r.get("refund_amount")), raw=d)]
        if t.startswith("SUBSCRIPTION_"):
            sub = data.get("subscription_details") or data
            sub_id = sub.get("subscription_id")
            status = str(sub.get("subscription_status", "")).upper()
            if t == "SUBSCRIPTION_PAYMENT_SUCCESS":
                p = data.get("payment") or data
                return [PaymentEvent("payment_captured", event_id, order_id=p.get("payment_id"),
                                     payment_id=str(p.get("cf_payment_id")), amount_minor=_minor(p.get("payment_amount")),
                                     currency="INR", mandate_ref=sub_id, raw=d)]
            if t == "SUBSCRIPTION_PAYMENT_FAILED":
                p = data.get("payment") or data
                return [PaymentEvent("payment_failed", event_id, order_id=p.get("payment_id"), mandate_ref=sub_id,
                                     error=p.get("failure_details", {}).get("failure_reason") if isinstance(
                                         p.get("failure_details"), dict) else None, raw=d)]
            kind = {"ACTIVE": "mandate_active", "CANCELLED": "mandate_cancelled"}.get(status, "mandate_failed")
            return [PaymentEvent(kind, event_id, mandate_token=sub_id, mandate_ref=sub_id, raw=d)]
        return []
