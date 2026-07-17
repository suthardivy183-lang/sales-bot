"""Pydantic models for the WhatsApp Cloud API webhook payload.

Only the fields the bot reads are modeled; unknown fields are ignored so
provider-side payload additions never break validation. `IncomingMessage` is
the provider-agnostic shape the rest of the system consumes — if the transport
provider changes (Twilio, 360dialog), only this module changes.
"""

from pydantic import BaseModel, ConfigDict, Field


class TextBody(BaseModel):
    body: str


class InboundMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    sender: str = Field(alias="from")
    timestamp: str
    type: str
    text: TextBody | None = None


class ChangeValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    messaging_product: str
    messages: list[InboundMessage] = []


class Change(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str
    value: ChangeValue


class Entry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    changes: list[Change] = []


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    object: str
    entry: list[Entry] = []


class IncomingMessage(BaseModel):
    """Normalized inbound text message, independent of the WhatsApp provider."""

    wa_id: str
    message_id: str
    text: str
    timestamp: str


def extract_incoming_messages(payload: WebhookPayload) -> list[IncomingMessage]:
    """Flatten a webhook payload into normalized text messages.

    Status-update payloads (delivered/read receipts) and non-text message types
    produce an empty list rather than an error — the webhook must always 200.
    """
    return [
        IncomingMessage(
            wa_id=message.sender,
            message_id=message.id,
            text=message.text.body,
            timestamp=message.timestamp,
        )
        for entry in payload.entry
        for change in entry.changes
        if change.field == "messages"
        for message in change.value.messages
        if message.type == "text" and message.text is not None
    ]
