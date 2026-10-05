from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Serviceability:
    serviceable: bool
    eta_days: int | None = None


@dataclass
class ShipmentRequest:
    reference: str  # booking code
    name: str
    phone_e164: str
    address: dict  # line1, line2, city, state, pincode, country
    items: list[dict]  # [{name, qty, unit_price_minor}]
    weight_kg: float = 0.3


@dataclass
class ShipmentRef:
    provider: str
    provider_order_id: str
    awb: str | None
    courier: str | None
    tracking_url: str | None
    label_url: str | None


@dataclass
class ShippingEvent:
    event_id: str
    awb: str
    status: str  # pending | packed | shipped | out_for_delivery | delivered | returned
    description: str = ""
    raw: dict = field(default_factory=dict)


class ShippingProvider(Protocol):
    name: str

    async def check_serviceability(self, pincode: str) -> Serviceability: ...

    async def create_shipment(self, req: ShipmentRequest) -> ShipmentRef: ...

    def parse_webhook(self, headers: dict, body: bytes) -> list[ShippingEvent]: ...
