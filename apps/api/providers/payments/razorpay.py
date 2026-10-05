"""Razorpay adapter — orders, UPI AutoPay (recurring tokens), refunds, webhooks.

Docs: https://razorpay.com/docs/api/ and
https://razorpay.com/docs/payments/payment-gateway/s2s-integration/recurring-payments/upi/
"""

import hashlib
import hmac
import json
from datetime import datetime

from providers.errors import WebhookVerificationError
from providers.messaging.http import request
from providers.payments.base import ChargeRef, Customer, MandateRef, OrderRef, PaymentEvent, RefundRef

API = "https://api.razorpay.com/v1"


class RazorpayProvider:
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str):
        self.key_id = key_id
        self.auth = (key_id, key_secret)
        self.webhook_secret = webhook_secret

    async def _post(self, path: str, body: dict) -> dict:
        return (await request("POST", f"{API}{path}", auth=self.auth, json=body)).json()

    async def create_order(self, booking_id, amount_minor, currency, customer: Customer, notes):
        data = await self._post("/orders", {
            "amount": amount_minor, "currency": currency, "receipt": str(notes.get("booking_code", booking_id))[:40],
            "notes": {k: str(v) for k, v in notes.items()},
        })
        return OrderRef("razorpay", data["id"], amount_minor, currency, checkout={
            "mode": "razorpay", "key": self.key_id, "order_id": data["id"], "amount": amount_minor,
            "currency": currency, "prefill": {"name": customer.name, "contact": customer.phone_e164,
                                              "email": customer.email or ""},
        })

    async def _customer(self, customer: Customer) -> str:
        data = await self._post("/customers", {"name": customer.name or "Devotee", "contact": customer.phone_e164,
                                               "email": customer.email or "", "fail_existing": "0"})
        return data["id"]

    async def create_mandate(self, subscription_id, max_amount_minor, frequency, start_at: datetime,
                             end_at: datetime, customer):
        customer_id = await self._customer(customer)
        # The first debit is authorised together with the mandate (PRD §8).
        data = await self._post("/orders", {
            "amount": max_amount_minor, "currency": "INR", "customer_id": customer_id, "method": "upi",
            "payment_capture": True, "receipt": subscription_id[:40],
            "token": {"max_amount": max_amount_minor, "expire_at": int(end_at.timestamp()),
                      "frequency": frequency},
            "notes": {"subscription_id": subscription_id},
        })
        order = OrderRef("razorpay", data["id"], max_amount_minor, "INR", checkout={
            "mode": "razorpay", "key": self.key_id, "order_id": data["id"], "customer_id": customer_id,
            "recurring": "1", "amount": max_amount_minor, "currency": "INR",
            "prefill": {"name": customer.name, "contact": customer.phone_e164},
        })
        # Token id arrives in payment.captured / token.confirmed; we store "customer_id:token_id".
        return MandateRef("razorpay", mandate_id=customer_id, token=None, status="created", first_order=order)

    async def charge_mandate(self, mandate_token, amount_minor, idempotency_key):
        customer_id, token_id = mandate_token.split(":", 1)
        order = await self._post("/orders", {"amount": amount_minor, "currency": "INR", "payment_capture": True,
                                             "receipt": idempotency_key[:40]})
        data = await self._post("/payments/create/recurring", {
            "amount": amount_minor, "currency": "INR", "order_id": order["id"], "customer_id": customer_id,
            "token": token_id, "recurring": "1", "notes": {"idempotency_key": idempotency_key},
            "contact": "", "email": "",
        })
        return ChargeRef("razorpay", order_id=order["id"], payment_id=data.get("razorpay_payment_id"),
                         status="created")

    async def cancel_mandate(self, mandate_token):
        customer_id, token_id = mandate_token.split(":", 1)
        await request("DELETE", f"{API}/customers/{customer_id}/tokens/{token_id}", auth=self.auth)

    async def refund(self, payment_id, amount_minor, reason, idempotency_key):
        data = await self._post(f"/payments/{payment_id}/refund", {
            "amount": amount_minor, "receipt": idempotency_key[:40], "notes": {"reason": reason[:250]},
        })
        return RefundRef("razorpay", data["id"], "processed" if data.get("status") == "processed" else "requested")

    def verify_webhook(self, headers, body):
        expected = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(headers.get("x-razorpay-signature", ""), expected):
            raise WebhookVerificationError("Razorpay signature mismatch")
        d = json.loads(body)
        event_id = headers.get("x-razorpay-event-id") or f"{d.get('event')}:{d.get('created_at')}"
        event = d.get("event", "")
        payload = d.get("payload", {})
        pay = (payload.get("payment") or {}).get("entity") or {}
        out: list[PaymentEvent] = []
        if event == "payment.captured":
            token = f"{pay['customer_id']}:{pay['token_id']}" if pay.get("token_id") and pay.get("customer_id") else None
            out.append(PaymentEvent("payment_captured", event_id, order_id=pay.get("order_id"),
                                    payment_id=pay.get("id"), amount_minor=pay.get("amount"),
                                    currency=pay.get("currency"), notes=pay.get("notes") or {},
                                    mandate_token=token, mandate_ref=pay.get("customer_id"), raw=d))
        elif event == "payment.failed":
            out.append(PaymentEvent("payment_failed", event_id, order_id=pay.get("order_id"), payment_id=pay.get("id"),
                                    amount_minor=pay.get("amount"), error=pay.get("error_description"),
                                    notes=pay.get("notes") or {}, raw=d))
        elif event in ("refund.processed", "refund.failed"):
            r = (payload.get("refund") or {}).get("entity") or {}
            out.append(PaymentEvent("refund_processed" if event == "refund.processed" else "refund_failed", event_id,
                                    payment_id=r.get("payment_id"), refund_id=r.get("id"),
                                    amount_minor=r.get("amount"), raw=d))
        elif event in ("token.confirmed", "token.rejected", "token.cancelled"):
            t = (payload.get("token") or {}).get("entity") or {}
            kind = {"token.confirmed": "mandate_active", "token.rejected": "mandate_failed",
                    "token.cancelled": "mandate_cancelled"}[event]
            out.append(PaymentEvent(kind, event_id, mandate_token=f"{t.get('customer_id')}:{t.get('id')}",
                                    mandate_ref=t.get("customer_id"), raw=d))
        return out
