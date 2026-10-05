from config import settings
from providers.messaging.base import MessagingProvider


def get_messaging_provider(name: str | None = None) -> MessagingProvider:
    name = name or settings.messaging_provider
    if name == "wati":
        from providers.messaging.wati import WatiProvider

        return WatiProvider(settings.wati_api_endpoint, settings.wati_access_token, settings.wati_webhook_token)
    if name == "gupshup":
        from providers.messaging.gupshup import GupshupProvider

        return GupshupProvider(settings.gupshup_api_key, settings.gupshup_app_name,
                               settings.gupshup_source_number, settings.gupshup_webhook_token)
    from providers.messaging.fake import FakeMessagingProvider

    return FakeMessagingProvider()
