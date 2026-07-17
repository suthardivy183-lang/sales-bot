"""Deterministic extraction of qualification fields from one message.

Rules run before any LLM pass (engineering rule 4): money amounts, BHK counts,
and known localities are parsed exactly, so an LLM can only fill fields the
rules left empty — never override them. Includes common Hinglish markers
("tak", "se upar", "chahiye") so code-switched input degrades gracefully.
"""

import re

from app.nlu.schemas import ExtractedFields
from app.state.models import Intent, Timeline

LAKH = 100_000
CRORE = 10_000_000
THOUSAND = 1_000

# Anything below 1 lakh is noise for a flat purchase, not a budget.
MIN_PLAUSIBLE_BUDGET = LAKH

_UNIT_VALUES = {
    "lakh": LAKH,
    "lakhs": LAKH,
    "lac": LAKH,
    "lacs": LAKH,
    "l": LAKH,
    "crore": CRORE,
    "crores": CRORE,
    "cr": CRORE,
    "k": THOUSAND,
}

_NUM = r"\d+(?:\.\d+)?"
_UNIT = r"lakhs?|lacs?|crores?|cr|l|k"

_RANGE_RE = re.compile(
    rf"(?:between\s+)?({_NUM})\s*({_UNIT})?(?:\s*[-–]\s*|\s+(?:to|and|se)\s+)({_NUM})\s*({_UNIT})\b",
    re.IGNORECASE,
)
_FLOOR_RE = re.compile(
    rf"(?:above|over|at\s+least|min(?:imum)?|more\s+than)\s+(?:rs\.?\s*)?({_NUM})\s*({_UNIT})\b",
    re.IGNORECASE,
)
_FLOOR_HINGLISH_RE = re.compile(
    rf"({_NUM})\s*({_UNIT})\s*se\s+(?:upar|zyada|jyada)\b", re.IGNORECASE
)
_CEILING_RE = re.compile(
    rf"(?:under|below|upto|up\s+to|max(?:imum)?|within|less\s+than|no\s+more\s+than)"
    rf"\s+(?:rs\.?\s*)?({_NUM})\s*({_UNIT})\b",
    re.IGNORECASE,
)
_CEILING_HINGLISH_RE = re.compile(rf"({_NUM})\s*({_UNIT})\s*tak\b", re.IGNORECASE)
_BARE_AMOUNT_RE = re.compile(rf"({_NUM})\s*({_UNIT})\b", re.IGNORECASE)
_PLAIN_RUPEES_RE = re.compile(r"\b(\d{6,})\b")

_BHK_DIGIT_RE = re.compile(r"\b(\d)\s*-?\s*(?:bhk|bed(?:room)?s?)\b", re.IGNORECASE)
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_BHK_WORD_RE = re.compile(
    rf"\b({'|'.join(_WORD_NUMBERS)})\s*-?\s*(?:bhk|bed(?:room)?s?)\b", re.IGNORECASE
)

# Canonical names must match the property fixtures exactly (Task 2 reuses this).
LOCALITY_ALIASES = {
    "bopal": "Bopal",
    "shela": "Shela",
    "satellite": "Satellite",
    "sg highway": "SG Highway",
    "s g highway": "SG Highway",
    "sarkhej gandhinagar highway": "SG Highway",
}

_RENT_RE = re.compile(r"\b(?:rent(?:al)?|lease|kiraya|kiraye)\b", re.IGNORECASE)
_BUY_RE = re.compile(
    r"\b(?:buy(?:ing)?|purchase|flat|apartment|house|home|property|invest(?:ment)?|chahiye)\b",
    re.IGNORECASE,
)

_IMMEDIATE_RE = re.compile(
    r"\b(?:immediate(?:ly)?|asap|urgent(?:ly)?|right\s+away|jaldi|ready\s+to\s+move)\b",
    re.IGNORECASE,
)
_MONTHS_RE = re.compile(r"\b(\d+)\s*months?\b", re.IGNORECASE)
_NEXT_MONTH_RE = re.compile(r"\bnext\s+month\b", re.IGNORECASE)
_YEARISH_RE = re.compile(r"\b(?:next\s+year|1\s*year|a\s+year)\b", re.IGNORECASE)


def _normalize(text: str) -> str:
    """Lowercase, join Indian-format digit groups, drop dots and currency markers."""
    result = text.lower()
    result = re.sub(r"(?<=\d),(?=\d)", "", result)
    # Drop dots (e.g. "s.g. highway") but preserve decimal points ("1.2 cr").
    result = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", result)
    result = result.replace("₹", " ")
    result = re.sub(r"\b(?:rs|inr)\b", " ", result)
    return re.sub(r"\s+", " ", result).strip()


def _amount(number: str, unit: str | None) -> int:
    return int(round(float(number) * _UNIT_VALUES.get((unit or "").lower(), 1)))


def extract_budget(text: str) -> tuple[int | None, int | None]:
    range_match = _RANGE_RE.search(text)
    if range_match:
        num_low, unit_low, num_high, unit_high = range_match.groups()
        low = _amount(num_low, unit_low or unit_high)
        high = _amount(num_high, unit_high)
        if low > high:
            low, high = high, low
        if high >= MIN_PLAUSIBLE_BUDGET:
            return low, high

    budget_min = None
    budget_max = None
    floor_match = _FLOOR_RE.search(text) or _FLOOR_HINGLISH_RE.search(text)
    if floor_match:
        budget_min = _amount(*floor_match.groups())
    ceiling_match = _CEILING_RE.search(text) or _CEILING_HINGLISH_RE.search(text)
    if ceiling_match:
        budget_max = _amount(*ceiling_match.groups())

    if budget_min is None and budget_max is None:
        bare_match = _BARE_AMOUNT_RE.search(text)
        if bare_match:
            budget_max = _amount(*bare_match.groups())
        else:
            plain_match = _PLAIN_RUPEES_RE.search(text)
            if plain_match:
                budget_max = int(plain_match.group(1))

    if budget_min is not None and budget_min < MIN_PLAUSIBLE_BUDGET:
        budget_min = None
    if budget_max is not None and budget_max < MIN_PLAUSIBLE_BUDGET:
        budget_max = None
    return budget_min, budget_max


def extract_bhk(text: str) -> int | None:
    digit_match = _BHK_DIGIT_RE.search(text)
    if digit_match:
        return int(digit_match.group(1))
    word_match = _BHK_WORD_RE.search(text)
    if word_match:
        return _WORD_NUMBERS[word_match.group(1).lower()]
    return None


def canonical_locality(name: str) -> str | None:
    """Map a free-form locality mention to its fixture-canonical name."""
    normalized = re.sub(r"\s+", " ", name.lower().replace(".", " ")).strip()
    return LOCALITY_ALIASES.get(normalized)


def extract_locality(text: str) -> str | None:
    normalized = _normalize(text)
    for alias in sorted(LOCALITY_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return LOCALITY_ALIASES[alias]
    return None


def extract_intent(text: str) -> Intent | None:
    if _RENT_RE.search(text):
        return Intent.RENT
    if _BUY_RE.search(text):
        return Intent.BUY
    return None


def extract_timeline(text: str) -> Timeline | None:
    if _IMMEDIATE_RE.search(text):
        return Timeline.IMMEDIATE
    if _NEXT_MONTH_RE.search(text):
        return Timeline.WITHIN_3_MONTHS
    if _YEARISH_RE.search(text):
        return Timeline.WITHIN_12_MONTHS
    months_match = _MONTHS_RE.search(text)
    if months_match:
        months = int(months_match.group(1))
        if months <= 3:
            return Timeline.WITHIN_3_MONTHS
        if months <= 6:
            return Timeline.WITHIN_6_MONTHS
        return Timeline.WITHIN_12_MONTHS
    return None


def extract_fields(text: str) -> ExtractedFields:
    normalized = _normalize(text)
    budget_min, budget_max = extract_budget(normalized)
    return ExtractedFields(
        intent=extract_intent(normalized),
        locality=extract_locality(text),
        budget_min=budget_min,
        budget_max=budget_max,
        bhk=extract_bhk(normalized),
        timeline=extract_timeline(normalized),
    )
