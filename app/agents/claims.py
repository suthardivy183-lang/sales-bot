"""Structured claims — the contract between generation and verification.

Every factual statement in a draft reply must appear here as a Claim tagged
with the property ID and source field it rests on (engineering rule 3).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.tools.emi import EMIQuote

ClaimValue = str | int | bool | None


class ClaimVerdict(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True)

    statement: str
    property_id: int
    evidence_field: str
    claimed_value: ClaimValue = None


class CheckedClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim: Claim
    verdict: ClaimVerdict
    actual_value: ClaimValue = None


class DraftReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    claims: tuple[Claim, ...] = ()
    emi_quote: EMIQuote | None = None


class VerifiedReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    approved: bool  # True only when the draft passed through unchanged
    escalate: bool  # True when an unsupported claim needs a human
    checked: tuple[CheckedClaim, ...] = ()
    emi_corrected: bool = False
