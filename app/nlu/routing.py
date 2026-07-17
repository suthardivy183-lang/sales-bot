"""Small-model cost routing (Task 10, optional).

In this system the deterministic rules already resolve most turns, so the
cheapest tier is literally *no LLM call*. The router picks one of three tiers
per turn from deterministic signals and logs the choice (the Task 10
done-when):

- RULES_ONLY — rules covered the message; skip the LLM entirely (free).
- SMALL      — a short, simple message the rules only partly parsed; a cheap
               model fills the gap.
- LARGE      — ambiguous, negotiation-heavy, long, or code-switched-with-no-
               rule-coverage; escalate to the stronger model.

The routing decision is pure (text + rule fields -> tier), so it is fully
testable without any API key. Model selection only matters once a key exists.
"""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.nlu.hinglish import is_code_switched
from app.nlu.rules import extract_fields
from app.nlu.schemas import ExtractedFields

SHORT_MESSAGE_WORDS = 8
LONG_MESSAGE_WORDS = 25

# Signals that a turn needs real reasoning, not a cheap single-field parse.
_ESCALATION_RE = re.compile(
    r"\b(?:but|however|actually|instead|rather|compare|versus|vs|confused|"
    r"not\s+sure|unsure|depends|negotiat\w*|discount|best\s+deal|lower\s+price|"
    r"which\s+(?:one|is\s+better)|trade[\s-]?off|either|or\s+should|"
    r"samajh\s+nahi|pata\s+nahi|thoda\s+kam)\b",
    re.IGNORECASE,
)


class RouteTier(StrEnum):
    RULES_ONLY = "rules_only"
    SMALL = "small"
    LARGE = "large"


class RouteDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: RouteTier
    model: str | None  # None for RULES_ONLY — no model is called
    reason: str


class ModelRouter:
    def __init__(self, small_model: str, large_model: str):
        self._small_model = small_model
        self._large_model = large_model

    def decide(
        self, text: str, rule_fields: ExtractedFields | None = None
    ) -> RouteDecision:
        fields = rule_fields if rule_fields is not None else extract_fields(text)
        rules_covered = fields != ExtractedFields()
        word_count = len(text.split())
        needs_reasoning = _ESCALATION_RE.search(text) is not None
        code_switched = is_code_switched(text)

        if needs_reasoning or word_count >= LONG_MESSAGE_WORDS:
            return RouteDecision(
                tier=RouteTier.LARGE,
                model=self._large_model,
                reason="negotiation/ambiguity or long message",
            )
        if rules_covered and not code_switched and word_count <= SHORT_MESSAGE_WORDS:
            return RouteDecision(
                tier=RouteTier.RULES_ONLY,
                model=None,
                reason="rules fully covered a short, unambiguous message",
            )
        if code_switched and not rules_covered:
            return RouteDecision(
                tier=RouteTier.LARGE,
                model=self._large_model,
                reason="code-switched with no rule coverage",
            )
        return RouteDecision(
            tier=RouteTier.SMALL,
            model=self._small_model,
            reason="short message with a parse gap",
        )
