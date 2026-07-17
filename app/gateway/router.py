"""Webhook endpoints for the WhatsApp gateway.

Task 0A: the POST handler validates a (mocked) WhatsApp payload and returns a
hardcoded reply in the response body so the round trip is testable locally.
Task 0B will replace the in-body reply with a real outbound send via the
provider API, keeping this handler's contract (always 200 for valid payloads).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.config import Settings, get_settings
from app.gateway.schemas import WebhookPayload, extract_incoming_messages
from app.privacy import mask_phone

logger = logging.getLogger(__name__)

router = APIRouter()

HARDCODED_REPLY = (
    "Namaste! Thanks for reaching out — I'm the Sales Copilot. "
    "I received your message and will be fully conversational soon."
)


@router.get("/webhook")
def verify_webhook(
    settings: Annotated[Settings, Depends(get_settings)],
    hub_mode: Annotated[str, Query(alias="hub.mode")] = "",
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")] = "",
    hub_challenge: Annotated[str, Query(alias="hub.challenge")] = "",
) -> PlainTextResponse:
    """Meta Cloud API webhook verification handshake (echo the challenge)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/webhook")
def receive_webhook(payload: WebhookPayload) -> dict:
    messages = extract_incoming_messages(payload)
    if not messages:
        # Delivery/read receipts and non-text messages: acknowledge and move on.
        return {"status": "ignored", "replies": []}

    for message in messages:
        logger.info("Inbound message from %s", mask_phone(message.wa_id))

    return {
        "status": "received",
        "replies": [
            {"to": mask_phone(message.wa_id), "reply": HARDCODED_REPLY}
            for message in messages
        ],
    }
