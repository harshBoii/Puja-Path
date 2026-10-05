from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol


@dataclass
class Customer:
    name: str
    phone_e164: str
    email: str | None = None


@dataclass
class OrderRef:
    provider: str
    order_id: str
    amount_minor: int
    currency: str
    checkout: dict = field(default_factory=dict)  # what the browser needs to open the gateway


@dataclass
class MandateRef:
    provider: str
    mandate_id: str  # provider-side id; token may arrive later by webhook
    token: str | None
    status: str  # created | active
    first_order: OrderRef | None = None


@dataclass
class ChargeRef:
    provider: str
    order_id: str | None
    payment_id: str | None
    status: str  # created | captured | failed


@dataclass
class RefundRef:
    provider: str
    refund_id: str
    status: str  # requested | processed


PaymentEventKind = Literal[
    "payment_captured", "payment_failed", "refund_processed", "refund_failed",
    "mandate_active", "mandate_failed", "mandate_cancelled",
]


@dataclass
class PaymentEvent:
    kind: PaymentEventKind
    event_id: str  # unique per provider event; dedupe key
    order_id: str | None = None
    payment_id: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    refund_id: str | None = None
    mandate_token: str | None = None
    mandate_ref: str | None = None
    notes: dict = field(default_factory=dict)
    error: str | None = None
    raw: dict = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    async def create_order(self, booking_id: str, amount_minor: int, currency: str,
                           customer: Customer, notes: dict) -> OrderRef: ...

    async def create_mandate(self, subscription_id: str, max_amount_minor: int,
                             frequency: str, start_at: datetime, end_at: datetime,
                             customer: Customer) -> MandateRef: ...

    async def charge_mandate(self, mandate_token: str, amount_minor: int,
                             idempotency_key: str) -> ChargeRef: ...

    async def cancel_mandate(self, mandate_token: str) -> None: ...

    async def refund(self, payment_id: str, amount_minor: int, reason: str,
                     idempotency_key: str) -> RefundRef: ...

    def verify_webhook(self, headers: dict, body: bytes) -> list[PaymentEvent]: ...
