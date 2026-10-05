from config import settings
from providers.payments.base import PaymentProvider


def get_payment_provider(name: str | None = None) -> PaymentProvider:
    name = name or settings.payment_provider
    if name == "razorpay":
        from providers.payments.razorpay import RazorpayProvider

        return RazorpayProvider(settings.razorpay_key_id, settings.razorpay_key_secret, settings.razorpay_webhook_secret)
    if name == "cashfree":
        from providers.payments.cashfree import CashfreeProvider

        return CashfreeProvider(settings.cashfree_app_id, settings.cashfree_secret_key,
                                settings.cashfree_webhook_secret, settings.cashfree_env)
    from providers.payments.fake import FakePaymentProvider

    return FakePaymentProvider(settings.fake_payment_webhook_secret)
