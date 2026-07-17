"""Qualification Agent: merges each turn's extraction into the session state.

Pure state-in/state-out — persistence stays with the caller, which makes the
multi-turn behaviour directly testable (Task 1 done-when).
"""

from app.nlu.hybrid import HybridExtractor
from app.nlu.schemas import ExtractedFields
from app.state.models import SessionState, Stage

QUALIFICATION_FIELDS = ("intent", "locality", "budget_max", "bhk")

_QUESTIONS = (
    ("intent", "Hi! Are you looking to buy a flat in Ahmedabad?"),
    ("budget_max", "What budget do you have in mind — for example, 'under 80 lakh'?"),
    ("locality", "Which area do you prefer — Bopal, Shela, Satellite, or SG Highway?"),
    ("bhk", "How many bedrooms are you looking for — 2BHK, 3BHK?"),
)


class QualificationAgent:
    def __init__(self, extractor: HybridExtractor):
        self._extractor = extractor

    def process_turn(self, state: SessionState, message_text: str) -> SessionState:
        extracted = self._extractor.extract(message_text, state)
        return apply_extraction(state, extracted)


def apply_extraction(
    state: SessionState, extracted: ExtractedFields
) -> SessionState:
    """Merge non-null extracted fields over the state; latest statement wins."""
    updates = {
        field: value
        for field, value in extracted.model_dump().items()
        if value is not None
    }
    merged = state.model_copy(update=updates)
    return merged.model_copy(update={"stage": _next_stage(merged)})


def _next_stage(state: SessionState) -> Stage:
    if state.stage not in (Stage.NEW, Stage.QUALIFYING, Stage.QUALIFIED):
        return state.stage  # never regress a lead that is already past qualification
    known = [
        field
        for field in QUALIFICATION_FIELDS
        if getattr(state, field) is not None
    ]
    if len(known) == len(QUALIFICATION_FIELDS):
        return Stage.QUALIFIED
    if known:
        return Stage.QUALIFYING
    return Stage.NEW


def next_question(state: SessionState) -> str | None:
    """The next thing to ask a not-yet-qualified lead, in demo order."""
    for field, question in _QUESTIONS:
        if getattr(state, field) is None:
            return question
    return None
