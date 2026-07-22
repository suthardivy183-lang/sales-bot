"""Webhook endpoints for the WhatsApp gateway.

Replies are computed by the Orchestrator and returned in the response body so
the whole flow is drivable locally. Task 0B swaps the in-body reply for a real
outbound send via the provider API, keeping this handler's contract.
"""

import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import Settings, get_settings
from app.gateway.client import WhatsAppSendError
from app.gateway.schemas import WebhookPayload, extract_incoming_messages
from app.privacy import mask_phone

logger = logging.getLogger(__name__)

WHATSAPP_REPLY_ACTION = "whatsapp_reply"

router = APIRouter()


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
async def receive_webhook(
    payload: WebhookPayload,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if settings.whatsapp_app_secret:
        raw_body = await request.body()
        signature = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    messages = extract_incoming_messages(payload)
    if not messages:
        # Delivery/read receipts and non-text messages: acknowledge and move on.
        return {"status": "ignored", "replies": []}

    orchestrator = request.app.state.orchestrator
    sender = request.app.state.whatsapp_sender
    reply_ledger = request.app.state.whatsapp_reply_ledger
    replies = []
    for message in messages:
        logger.info("Inbound message from %s", mask_phone(message.wa_id))
        replayed = reply_ledger.get(message.message_id, WHATSAPP_REPLY_ACTION)
        if replayed is not None:
            replies.append(
                {
                    "to": mask_phone(message.wa_id),
                    "reply": replayed["reply"],
                    "delivered": True,
                }
            )
            continue

        reply = orchestrator.handle_message(message)
        delivered = False
        if sender is not None:
            try:
                sender.send_text(message.wa_id, reply)
                delivered = True
                reply_ledger.record(
                    message.message_id,
                    WHATSAPP_REPLY_ACTION,
                    {"reply": reply},
                )
            except WhatsAppSendError as exc:
                logger.error(
                    "WhatsApp reply delivery failed for %s: %s",
                    mask_phone(message.wa_id),
                    exc,
                )
        replies.append(
            {
                "to": mask_phone(message.wa_id),
                "reply": reply,
                "delivered": delivered,
            }
        )
    return {"status": "received", "replies": replies}
