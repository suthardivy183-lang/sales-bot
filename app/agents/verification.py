"""Verification Agent — the gate between drafting and sending.

Every structured claim is checked deterministically against the property
record (engineering rules 3 and 4):

- SUPPORTED     -> the claim may ship as stated.
- CONTRADICTED  -> the record disagrees; the reply is rewritten with the
                   record's value (the verifier has the evidence in hand).
- UNSUPPORTED   -> no evidence field exists (or it is empty); the claim is
                   refused outright and flagged for human follow-up.

EMI quotes are re-computed from their own inputs — an invented or tampered
number is corrected deterministically, never trusted.

Free-text soft claims ("great for families") are out of scope for this
deterministic gate; an LLM judgment pass is a designed extension, not built.
"""

from app.agents.claims import (
    CheckedClaim,
    Claim,
    ClaimVerdict,
    ClaimValue,
    DraftReply,
    VerifiedReply,
)
from app.inr import format_inr
from app.properties.models import Property
from app.properties.repository import PropertyRepository
from app.tools.emi import EMIQuote, calculate_emi

ESCALATION_NOTE = (
    "I've flagged this for a human agent to confirm with the builder."
)


class VerificationAgent:
    def __init__(self, repository: PropertyRepository):
        self._repository = repository

    def verify(self, draft: DraftReply) -> VerifiedReply:
        checked = tuple(self._check(claim) for claim in draft.claims)
        corrected_quote = (
            _recompute_emi(draft.emi_quote) if draft.emi_quote else None
        )
        emi_ok = corrected_quote is None or corrected_quote == draft.emi_quote

        all_supported = all(
            item.verdict == ClaimVerdict.SUPPORTED for item in checked
        )
        if all_supported and emi_ok:
            return VerifiedReply(
                text=draft.text, approved=True, escalate=False, checked=checked
            )

        escalate = any(
            item.verdict == ClaimVerdict.UNSUPPORTED for item in checked
        )
        text = _conservative_text(
            checked, None if emi_ok else corrected_quote
        )
        return VerifiedReply(
            text=text,
            approved=False,
            escalate=escalate,
            checked=checked,
            emi_corrected=not emi_ok,
        )

    def _check(self, claim: Claim) -> CheckedClaim:
        prop = self._repository.get(claim.property_id)
        if prop is None:
            return CheckedClaim(claim=claim, verdict=ClaimVerdict.UNSUPPORTED)
        if claim.evidence_field not in Property.model_fields:
            return CheckedClaim(claim=claim, verdict=ClaimVerdict.UNSUPPORTED)
        actual = getattr(prop, claim.evidence_field)
        if actual is None:
            return CheckedClaim(claim=claim, verdict=ClaimVerdict.UNSUPPORTED)
        actual_value = actual.value if hasattr(actual, "value") else actual
        if _values_match(claim.claimed_value, actual_value):
            return CheckedClaim(
                claim=claim,
                verdict=ClaimVerdict.SUPPORTED,
                actual_value=actual_value,
            )
        return CheckedClaim(
            claim=claim,
            verdict=ClaimVerdict.CONTRADICTED,
            actual_value=actual_value,
        )


def _values_match(claimed: ClaimValue, actual: ClaimValue) -> bool:
    return str(claimed).strip().lower() == str(actual).strip().lower()


def _recompute_emi(quote: EMIQuote) -> EMIQuote:
    return calculate_emi(
        quote.principal, quote.annual_rate_percent, quote.tenure_months
    )


def _display_value(field: str, value: ClaimValue) -> str:
    if field == "price" and isinstance(value, int):
        return format_inr(value)
    return str(value).replace("_", " ")


def _conservative_text(
    checked: tuple[CheckedClaim, ...], corrected_quote: EMIQuote | None
) -> str:
    unsupported = [c for c in checked if c.verdict == ClaimVerdict.UNSUPPORTED]
    contradicted = [c for c in checked if c.verdict == ClaimVerdict.CONTRADICTED]
    supported = [c for c in checked if c.verdict == ClaimVerdict.SUPPORTED]

    parts: list[str] = []
    if unsupported:
        listed = " or ".join(item.claim.statement for item in unsupported)
        parts.append(
            f"I can't confirm {listed} from the verified listing data, "
            f"so I won't state it as fact. {ESCALATION_NOTE}"
        )
    for item in contradicted:
        field = item.claim.evidence_field
        parts.append(
            f"Correction: the listed {field.replace('_', ' ')} is "
            f"{_display_value(field, item.actual_value)}."
        )
    if corrected_quote is not None:
        parts.append(
            f"Correction: the EMI works out to "
            f"₹{corrected_quote.monthly_emi:,}/month for a loan of "
            f"{format_inr(corrected_quote.principal)} at "
            f"{corrected_quote.annual_rate_percent:g}% p.a. over "
            f"{corrected_quote.tenure_months // 12} years."
        )
    if supported:
        confirmed = "; ".join(item.claim.statement for item in supported)
        parts.append(f"What I can confirm from the listing: {confirmed}.")
    return "\n".join(parts)
