"""Property records — the single source of truth every claim is verified against."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PossessionStatus(StrEnum):
    READY_TO_MOVE = "ready_to_move"
    UNDER_CONSTRUCTION = "under_construction"


class Property(BaseModel):
    """One listing. extra="forbid" so a fixture typo fails loudly at load time,
    and absent fields (e.g. private_pool) stay absent — the Verification Agent
    depends on that to catch unsupported claims."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int
    bhk: int
    locality: str
    price: int
    status: PossessionStatus
    possession: str | None = None
