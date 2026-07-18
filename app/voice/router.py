"""Thin ElevenLabs voice transport adapter for the Sales Copilot."""

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.gateway.schemas import IncomingMessage
from app.privacy import mask_phone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice/elevenlabs")


class ElevenLabsVoicePayload(BaseModel):
    """Normalized transcript event forwarded by the ElevenLabs agent tool."""

    caller_phone_number: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    transcript: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)


@router.post("/webhook")
def receive_voice_webhook(payload: ElevenLabsVoicePayload, request: Request) -> dict:
    """Send one spoken turn through the same orchestrator as WhatsApp."""
    message = IncomingMessage(
        wa_id=payload.caller_phone_number,
        message_id=payload.event_id,
        text=payload.transcript,
        timestamp=payload.timestamp,
    )
    logger.info("Inbound voice transcript from %s", mask_phone(message.wa_id))
    reply = request.app.state.orchestrator.handle_message(message)
    return {"reply": reply}
