class ProviderError(Exception):
    """Permanent provider error — do not retry."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class RetryableProviderError(ProviderError):
    """Timeouts and 5xx — retry with backoff."""


class WebhookVerificationError(Exception):
    pass
