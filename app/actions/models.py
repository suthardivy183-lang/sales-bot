"""Action tool records. CRM rows carry MASKED numbers only — the demo video
shows the live sheet, and a full phone number must never appear there
(engineering rule 8)."""

from pydantic import BaseModel, ConfigDict


class CrmError(RuntimeError):
    """CRM backend failure (network, auth, quota)."""


class SlotUnavailableError(RuntimeError):
    """No viewing slot left to book."""


class CrmLead(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    wa_id_masked: str
    intent: str | None = None
    locality: str | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    bhk: int | None = None
    timeline: str | None = None
    stage: str
    property_id: int | None = None
    note: str = ""
    created_at: str


class CrmWriteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: bool  # False on an idempotent replay
    lead: CrmLead


class Slot(BaseModel):
    model_config = ConfigDict(frozen=True)

    slot_id: str
    label: str


class BookingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: bool  # False on an idempotent replay
    slot_id: str
    slot_label: str
    wa_id_masked: str
    message_id: str
