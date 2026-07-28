"""Thin ElevenLabs voice transport adapter for the Sales Copilot."""

from hmac import compare_digest
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.gateway.schemas import IncomingMessage
from app.privacy import mask_phone

logger = logging.getLogger(__name__)

VOICE_REPLY_ACTION = "elevenlabs_voice_reply"

router = APIRouter(prefix="/voice/elevenlabs")
VOICE_WEBHOOK_SECRET_HEADER = "X-Voice-Webhook-Secret"


class ElevenLabsVoicePayload(BaseModel):
    """Normalized transcript event forwarded by the ElevenLabs agent tool."""

    caller_phone_number: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    transcript: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)


@router.post("/webhook")
def receive_voice_webhook(
    payload: ElevenLabsVoicePayload,
    request: Request,
    voice_webhook_secret: str | None = Header(
        default=None, alias=VOICE_WEBHOOK_SECRET_HEADER
    ),
) -> dict:
    """Send one spoken turn through the same orchestrator as WhatsApp."""
    expected_secret = request.app.state.settings.elevenlabs_webhook_secret
    if expected_secret and not compare_digest(voice_webhook_secret or "", expected_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid voice webhook secret",
        )

    reply_ledger = request.app.state.voice_reply_ledger
    replayed = reply_ledger.get(payload.event_id, VOICE_REPLY_ACTION)
    if replayed is not None:
        return {"reply": replayed["reply"]}

    message = IncomingMessage(
        wa_id=payload.caller_phone_number,
        message_id=payload.event_id,
        text=payload.transcript,
        timestamp=payload.timestamp,
    )
    logger.info("Inbound voice transcript from %s", mask_phone(message.wa_id))
    reply = request.app.state.orchestrator.handle_message(message)
    reply_ledger.record(payload.event_id, VOICE_REPLY_ACTION, {"reply": reply})
    return {"reply": reply}
