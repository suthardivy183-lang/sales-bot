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


def wants_booking(text: str) -> bool:
    return _BOOKING_RE.search(text) is not None


def wants_emi(text: str) -> bool:
    return _EMI_RE.search(text) is not None
