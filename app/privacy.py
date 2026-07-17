"""PII masking helpers. Raw phone numbers must never reach logs or API responses."""

VISIBLE_SUFFIX_LENGTH = 4


def mask_phone(number: str) -> str:
    """Mask all but the last 4 digits of a phone number / WhatsApp ID."""
    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) <= VISIBLE_SUFFIX_LENGTH:
        return "*" * len(digits)
    return "*" * (len(digits) - VISIBLE_SUFFIX_LENGTH) + digits[-VISIBLE_SUFFIX_LENGTH:]
