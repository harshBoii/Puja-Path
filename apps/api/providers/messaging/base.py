from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass
class TemplateRef:
    key: str  # our template key, e.g. booking_confirmed
    locale: str
    provider_ref: str  # WATI template name or Gupshup template UUID
    variables: list[str] = field(default_factory=list)  # our variable names, in order


@dataclass
class SendResult:
    provider_message_id: str | None
    accepted: bool
    error: str | None = None


EventKind = Literal["sent", "delivered", "read", "failed", "inbound_text", "inbound_button"]


@dataclass
class MessagingEvent:
    kind: EventKind
    provider_message_id: str | None = None
    from_e164: str | None = None
    text: str | None = None
    button_payload: str | None = None
    error_code: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ProviderTemplate:
    provider_ref: str
    name: str
    locale: str | None
    status: str  # approved | pending | rejected
    category: str | None = None


# WhatsApp error codes that mean the number cannot receive messages — the booking goes to the ops call queue.
INVALID_NUMBER_CODES = {"131026", "131021", "1013", "invalid_number"}


class MessagingProvider(Protocol):
    name: str

    async def send_template(
        self,
        to: str,
        template: TemplateRef,
        params: list[str],
        header_media_url: str | None = None,
        button_params: list[str] | None = None,
        idempotency_key: str = "",
    ) -> SendResult: ...

    async def send_session_text(self, to: str, text: str) -> SendResult: ...

    def parse_webhook(self, headers: dict, body: bytes) -> list[MessagingEvent]: ...

    async def list_templates(self) -> list[ProviderTemplate]: ...


def digits(e164: str) -> str:
    return e164.lstrip("+")
