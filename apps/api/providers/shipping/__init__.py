from config import settings
from providers.shipping.base import ShippingProvider


def get_shipping_provider(name: str | None = None) -> ShippingProvider:
    name = name or settings.shipping_provider
    if name == "shiprocket":
        from providers.shipping.shiprocket import ShiprocketProvider

        return ShiprocketProvider(settings.shiprocket_email, settings.shiprocket_password,
                                  settings.shiprocket_pickup_location, settings.shiprocket_pickup_pincode,
                                  settings.shiprocket_webhook_token)
    from providers.shipping.fake import FakeShippingProvider

    return FakeShippingProvider()
