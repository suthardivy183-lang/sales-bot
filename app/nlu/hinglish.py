"""Code-switch detection for Hindi/Hinglish input.

Detection is a signal, not a gate: the rule extractor handles romanized
Hinglish natively, and the LLM extractor (when configured) covers phrasings
the rules can't. This flag feeds logging today and small-model routing
(Task 10) later. Common Hindi-script BHK, buy, and rent cues are handled by
the deterministic rules; broader Hindi understanding remains an extension.
"""

import re

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

_MARKERS = (
    "chahiye", "hai", "mein", "tak", "se upar", "ke andar", "se kam",
    "kitna", "kitne", "lena", "dekhna", "dekhne", "ghar", "makaan",
    "kamra", "kamre", "mahine", "mahina", "turant", "jaldi", "abhi",
    "sasta", "kiraya", "kiraye", "zyada", "jyada", "aas paas",
    "bataiye", "theek", "accha", "nahi", "nahin",
)
_MARKER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(marker) for marker in _MARKERS) + r")\b",
    re.IGNORECASE,
)


def is_code_switched(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text)) or bool(_MARKER_RE.search(text))
