import json
import random
import uuid

from providers.errors import WebhookVerificationError
from providers.recorder import record
from providers.shipping.base import Serviceability, ShipmentRef, ShippingEvent


class FakeShippingProvider:
    """Pincodes starting with 9 (Army Postal Service range) are treated as unserviceable."""

    name = "fake"

    def __init__(self, webhook_token: str = "fake-token"):
        self.webhook_token = webhook_token

    async def check_serviceability(self, pincode):
        await record("shipping", "check_serviceability", {"pincode": pincode})
        ok = len(pincode) == 6 and pincode.isdigit() and pincode[0] != "9" and pincode[0] != "0"
        return Serviceability(ok, eta_days=4 if ok else None)

    async def create_shipment(self, req):
        awb = f"FAKE{random.randint(10**9, 10**10 - 1)}"
        order_id = f"fake_ship_{uuid.uuid4().hex[:10]}"
        await record("shipping", "create_shipment", {"reference": req.reference, "awb": awb, "order_id": order_id,
                                                     "address": req.address, "items": req.items})
        return ShipmentRef("fake", order_id, awb, "Fake Express", f"https://example.invalid/track/{awb}",
                           label_url=None)

    def parse_webhook(self, headers, body):
        if headers.get("x-fake-token") != self.webhook_token:
            raise WebhookVerificationError("bad token")
        d = json.loads(body)
        return [ShippingEvent(event_id=d.get("event_id") or uuid.uuid4().hex, awb=d["awb"], status=d["status"],
                              description=d.get("description", ""), raw=d)]
