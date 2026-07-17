"""LLM-backed extraction for phrasings the deterministic rules can't parse.

Output is strictly validated: unknown enum values become None, localities are
canonicalized, and any provider failure degrades to an empty extraction so a
turn never crashes on the LLM's account.
"""

import logging

from app.llm.provider import LLMProvider, LLMProviderError
from app.nlu.rules import canonical_locality
from app.nlu.schemas import ExtractedFields
from app.state.models import Intent, SessionState, Timeline

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract real-estate lead qualification fields from one WhatsApp message.
The customer may write in English, Hindi, or Hinglish.
Return ONLY a JSON object with exactly these keys:
{"intent": "buy"|"rent"|null, "locality": string|null, "budget_min": integer|null,
 "budget_max": integer|null, "bhk": integer|null,
 "timeline": "immediate"|"within_3_months"|"within_6_months"|"within_12_months"|null}
Budgets are absolute INR (e.g. "70 lakh" -> 7000000, "1.2 cr" -> 12000000).
A bare budget like "70 lakh budget" means budget_max.
Use null for anything the message does not state. Never guess."""


class LLMExtractor:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    def extract(
        self, text: str, state: SessionState | None = None
    ) -> ExtractedFields:
        known = (
            state.model_dump(include={"intent", "locality", "budget_max", "bhk"})
            if state
            else {}
        )
        try:
            data = self._provider.generate_json(
                system=SYSTEM_PROMPT,
                user=f"Already known (do not repeat unless corrected): {known}\nMessage: {text}",
            )
        except LLMProviderError as exc:
            logger.warning("LLM extraction unavailable, using rules only: %s", exc)
            return ExtractedFields()
        return _validated(data)


def _validated(data: dict) -> ExtractedFields:
    return ExtractedFields(
        intent=_coerce_enum(Intent, data.get("intent")),
        locality=_coerce_locality(data.get("locality")),
        budget_min=_coerce_amount(data.get("budget_min")),
        budget_max=_coerce_amount(data.get("budget_max")),
        bhk=_coerce_int(data.get("bhk")),
        timeline=_coerce_enum(Timeline, data.get("timeline")),
    )


def _coerce_enum(enum_cls, value):
    try:
        return enum_cls(value)
    except ValueError:
        return None


def _coerce_locality(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    # Canonical fixture name when known; otherwise keep the raw mention so the
    # search tool can honestly report "no properties there".
    return canonical_locality(value) or value.strip()


def _coerce_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _coerce_amount(value) -> int | None:
    amount = _coerce_int(value)
    return amount if amount is not None and amount > 0 else None
