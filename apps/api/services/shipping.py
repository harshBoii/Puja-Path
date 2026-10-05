"""Prasad shipping sub-machine (PRD §6). A booking without prasad never waits on a courier."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logging_setup import log
from models import Booking, BookingStatus, Shipment, ShipmentStatus
from providers.shipping import get_shipping_provider
from providers.shipping.base import ShipmentRequest, ShippingEvent
from services import bookings as booking_svc
from services import notify
from services.audit import audit
from services.catalog import puja_title
from services.i18n import utcnow

logger = logging.getLogger("shipping")
SS = ShipmentStatus
_ORDER = [SS.pending, SS.packed, SS.shipped, SS.out_for_delivery, SS.delivered]
_TEMPLATES = {SS.shipped: "prasad_shipped", SS.out_for_delivery: "prasad_out_for_delivery",
              SS.delivered: "prasad_delivered"}


async def bulk_create(db: AsyncSession, event_id: int, staff_id: int) -> dict:
    provider = get_shipping_provider()
    rows = (await db.execute(
        select(Shipment, Booking).join(Booking, Shipment.booking_id == Booking.id)
        .where(Booking.puja_event_id == event_id, Shipment.status == SS.pending,
               Booking.status.not_in([BookingStatus.cancelled, BookingStatus.refunded, BookingStatus.draft,
                                      BookingStatus.pending_payment]))
    )).all()
    created, failed = [], []
    for sh, b in rows:
        items = [{"name": "Prasad box", "qty": 1, "unit_price_minor": b.shipping_minor or 0}]
        items += [{"name": f"Offering #{a.addon_item_id}", "qty": a.qty, "unit_price_minor": a.unit_price_minor}
                  for a in b.addons if a.item and a.item.ships_home]
        try:
            ref = await provider.create_shipment(ShipmentRequest(
                reference=b.code, name=sh.address.get("name") or (b.names[0].name if b.names else ""),
                phone_e164=sh.address.get("phone") or b.whatsapp_e164 or "", address=sh.address, items=items))
        except Exception as e:  # noqa: BLE001
            failed.append({"code": b.code, "error": str(e)[:200]})
            continue
        sh.provider, sh.provider_order_id, sh.awb = ref.provider, ref.provider_order_id, ref.awb
        sh.courier, sh.tracking_url, sh.label_url = ref.courier, ref.tracking_url, ref.label_url
        sh.status = SS.packed
        sh.events = [*sh.events, {"status": "packed", "at": utcnow().isoformat()}]
        created.append(b.code)
        log(logger, "shipment created", booking_id=str(b.id), awb=ref.awb)
    await audit(db, staff_id, "shipping.bulk_create", "puja_event", event_id, {"created": created, "failed": failed})
    return {"created": created, "failed": failed}


async def apply_event(db: AsyncSession, ev: ShippingEvent) -> None:
    sh = (await db.execute(select(Shipment).where(Shipment.awb == ev.awb).with_for_update())).scalar_one_or_none()
    if sh is None:
        return
    new = SS(ev.status)
    sh.events = [*sh.events, {"status": ev.status, "desc": ev.description, "at": utcnow().isoformat()}]
    if new == SS.returned:
        sh.status = new
        return
    if new in _ORDER and sh.status in _ORDER and _ORDER.index(new) <= _ORDER.index(sh.status):
        return  # out-of-order or repeated event
    sh.status = new
    b = await db.get(Booking, sh.booking_id)
    log(logger, "shipment status", booking_id=str(b.id), status=ev.status)
    title = await puja_title(db, b.event.puja_id, b.locale)
    tpl = _TEMPLATES.get(new)
    if tpl == "prasad_shipped":
        await notify.queue(db, template_key=tpl, to=b.whatsapp_e164, locale=b.locale, booking=b,
                           params=[title, sh.courier or "", sh.awb or ""], button_params=[sh.tracking_url or ""])
    elif tpl == "prasad_out_for_delivery":
        await notify.queue(db, template_key=tpl, to=b.whatsapp_e164, locale=b.locale, booking=b,
                           params=[sh.courier or "", sh.awb or ""], button_params=[sh.tracking_url or ""])
    elif tpl == "prasad_delivered":
        await notify.queue(db, template_key=tpl, to=b.whatsapp_e164, locale=b.locale, booking=b, params=[title])
        await booking_svc.maybe_complete(db, b)
