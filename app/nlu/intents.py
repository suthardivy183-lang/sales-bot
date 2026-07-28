"""Per-turn action intents (distinct from the buy/rent lead intent)."""

import re

_BOOKING_RE = re.compile(
    r"\b(?:book(?:ing)?|schedule|visit|viewing|site\s+visit|appointment|dekhna|dekhne)\b",
    re.IGNORECASE,
)
_EMI_RE = re.compile(
    r"\b(?:emi|installments?|instalments?|loan|monthly\s+payment|kist)\b",
    re.IGNORECASE,
)
_HUMAN_HANDOFF_RE = re.compile(
    r"\b(?:human(?:\s+agent)?|agent|representative|real\s+person|talk\s+to\s+(?:a\s+)?(?:person|someone)|call\s+me)\b|"
    r"(?:insaan|aadmi|baat\s+(?:karni|karna)\s+hai)",
    re.IGNORECASE,
)
_NEGOTIATION_RE = re.compile(
    r"\b(?:discount|negotiate|negotiation|best\s+price|lower\s+price|too\s+expensive|better\s+deal)\b|"
    r"(?:kam\s+karo|sasta\s+karo|rate\s+kam)",
    re.IGNORECASE,
)


def wants_booking(text: str) -> bool:
    return _BOOKING_RE.search(text) is not None


def wants_emi(text: str) -> bool:
    return _EMI_RE.search(text) is not None


def handoff_reason(text: str) -> str | None:
    """Return a deterministic escalation reason for a sales-sensitive turn."""
    if _HUMAN_HANDOFF_RE.search(text) is not None:
        return "caller requested a human sales agent"
    if _NEGOTIATION_RE.search(text) is not None:
        return "caller requested price negotiation"
    return None
