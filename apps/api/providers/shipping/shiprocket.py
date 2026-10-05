"""Shiprocket adapter — https://apidocs.shiprocket.in/"""

import hmac
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from providers.errors import ProviderError, WebhookVerificationError
from providers.messaging.http import request
from providers.shipping.base import Serviceability, ShipmentRef, ShippingEvent

API = "https://apiv2.shiprocket.in/v1/external"
IST = ZoneInfo("Asia/Kolkata")

_STATUS_MAP = {
    "PICKUP SCHEDULED": "packed", "PICKUP GENERATED": "packed", "PICKUP QUEUED": "packed", "MANIFESTED": "packed",
    "PICKED UP": "shipped", "SHIPPED": "shipped", "IN TRANSIT": "shipped", "REACHED AT DESTINATION HUB": "shipped",
    "OUT FOR DELIVERY": "out_for_delivery", "DELIVERED": "delivered",
}


def map_status(text: str) -> str | None:
    t = (text or "").upper().strip()
    if t.startswith("RTO"):
        return "returned"
    return _STATUS_MAP.get(t)


class ShiprocketProvider:
    name = "shiprocket"

    def __init__(self, email: str, password: str, pickup_location: str, pickup_pincode: str, webhook_token: str):
        self.email = email
        self.password = password
        self.pickup_location = pickup_location
        self.pickup_pincode = pickup_pincode
        self.webhook_token = webhook_token
        self._token: str | None = None
        self._token_at = 0.0

    async def _auth(self) -> dict:
        # Tokens are valid ~10 days; refresh daily.
        if not self._token or time.time() - self._token_at > 86400:
            resp = await request("POST", f"{API}/auth/login", json={"email": self.email, "password": self.password})
            self._token = resp.json()["token"]
            self._token_at = time.time()
        return {"Authorization": f"Bearer {self._token}"}

    async def check_serviceability(self, pincode):
        resp = await request("GET", f"{API}/courier/serviceability/", headers=await self._auth(), params={
            "pickup_postcode": self.pickup_pincode, "delivery_postcode": pincode, "weight": 0.5, "cod": 0,
        })
        couriers = (resp.json().get("data") or {}).get("available_courier_companies") or []
        if not couriers:
            return Serviceability(False)
        eta = min((int(c.get("estimated_delivery_days") or 7) for c in couriers), default=None)
        return Serviceability(True, eta)

    async def create_shipment(self, req):
        headers = await self._auth()
        a = req.address
        order = (await request("POST", f"{API}/orders/create/adhoc", headers=headers, json={
            "order_id": req.reference, "order_date": datetime.now(IST).date().isoformat(),
            "pickup_location": self.pickup_location,
            "billing_customer_name": req.name, "billing_last_name": "", "billing_address": a.get("line1", ""),
            "billing_address_2": a.get("line2", ""), "billing_city": a.get("city", ""),
            "billing_pincode": a.get("pincode", ""), "billing_state": a.get("state", ""),
            "billing_country": "India", "billing_phone": req.phone_e164[-10:], "shipping_is_billing": True,
            "order_items": [{"name": i["name"], "sku": i.get("sku", i["name"][:20]), "units": i["qty"],
                             "selling_price": i["unit_price_minor"] / 100} for i in req.items],
            "payment_method": "Prepaid", "sub_total": sum(i["qty"] * i["unit_price_minor"] for i in req.items) / 100,
            "length": 15, "breadth": 12, "height": 6, "weight": req.weight_kg,
        })).json()
        shipment_id = order.get("shipment_id")
        if not shipment_id:
            raise ProviderError(f"Shiprocket order failed: {order}")
        awb_resp = (await request("POST", f"{API}/courier/assign/awb", headers=headers,
                                  json={"shipment_id": shipment_id})).json()
        awb_data = (awb_resp.get("response") or {}).get("data") or {}
        label = (await request("POST", f"{API}/courier/generate/label", headers=headers,
                               json={"shipment_id": [shipment_id]})).json()
        awb = awb_data.get("awb_code")
        return ShipmentRef("shiprocket", str(shipment_id), awb, awb_data.get("courier_name"),
                           f"https://shiprocket.co/tracking/{awb}" if awb else None, label.get("label_url"))

    def parse_webhook(self, headers, body):
        token = headers.get("x-api-key", "")
        if not self.webhook_token or not hmac.compare_digest(token, self.webhook_token):
            raise WebhookVerificationError("Shiprocket token mismatch")
        d = json.loads(body)
        status = map_status(d.get("current_status") or d.get("shipment_status") or "")
        if not status or not d.get("awb"):
            return []
        event_id = f"{d.get('awb')}:{d.get('current_status')}:{d.get('current_timestamp') or d.get('etd')}"
        return [ShippingEvent(event_id=event_id, awb=str(d["awb"]), status=status,
                              description=d.get("current_status", ""), raw=d)]
