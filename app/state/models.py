"""Domain enums and the per-lead conversation state (engineering rule 1)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Intent(StrEnum):
    BUY = "buy"
    RENT = "rent"


class Timeline(StrEnum):
    IMMEDIATE = "immediate"
    WITHIN_3_MONTHS = "within_3_months"
    WITHIN_6_MONTHS = "within_6_months"
    WITHIN_12_MONTHS = "within_12_months"


class Stage(StrEnum):
    NEW = "new"
    QUALIFYING = "qualifying"
    QUALIFIED = "qualified"
    MATCHED = "matched"
    BOOKED = "booked"
    HANDOFF = "handoff"


class SessionState(BaseModel):
    """One lead's running picture, keyed by WhatsApp number.

    Frozen: every turn produces a new state object via model_copy, never an
    in-place mutation.
    """

    model_config = ConfigDict(frozen=True)

    session_id: str
    wa_id: str
    intent: Intent | None = None
    locality: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    bhk: int | None = None
    timeline: Timeline | None = None
    selected_property_id: int | None = None
    stage: Stage = Stage.NEW
