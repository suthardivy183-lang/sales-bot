"""Property Search Tool — hybrid retrieval (engineering rule 2).

Hard filters (BHK, locality, price ceiling, possession status) are applied
deterministically first. The preference reranker may only REORDER the already
filtered candidates; it can never add a property back or drop one. Reranking
is keyword-heuristic for the hackathon — an embedding/LLM reranker can slot in
behind the same function signature without touching the filters.
"""

from pydantic import BaseModel, ConfigDict

from app.nlu.rules import canonical_locality
from app.properties.models import PossessionStatus, Property
from app.state.models import SessionState, Timeline


class SearchCriteria(BaseModel):
    model_config = ConfigDict(frozen=True)

    bhk: int | None = None
    locality: str | None = None
    budget_max: int | None = None
    status: PossessionStatus | None = None


def criteria_from_state(state: SessionState) -> SearchCriteria:
    """Map the qualified lead state onto hard search criteria.

    An "immediate" timeline hard-filters to ready-to-move stock: a lead who
    must move now genuinely cannot use an under-construction flat.
    """
    return SearchCriteria(
        bhk=state.bhk,
        locality=state.locality,
        budget_max=state.budget_max,
        status=(
            PossessionStatus.READY_TO_MOVE
            if state.timeline == Timeline.IMMEDIATE
            else None
        ),
    )


def hard_filter(
    properties: tuple[Property, ...], criteria: SearchCriteria
) -> list[Property]:
    return [
        prop
        for prop in properties
        if (criteria.bhk is None or prop.bhk == criteria.bhk)
        and (criteria.locality is None or _same_locality(prop.locality, criteria.locality))
        and (criteria.budget_max is None or prop.price <= criteria.budget_max)
        and (criteria.status is None or prop.status == criteria.status)
    ]


def _same_locality(property_locality: str, wanted: str) -> bool:
    canonical = canonical_locality(wanted)
    return property_locality.lower() == (canonical or wanted).lower()


# Preference keywords -> sort key over structured fields. Deliberately built on
# real record fields so the ordering is explainable, never invented.
_POSSESSION_FALLBACK = "9999-99"  # sorts after any real YYYY-MM possession date


def _readiness_key(prop: Property):
    return (
        prop.status != PossessionStatus.READY_TO_MOVE,
        prop.possession or _POSSESSION_FALLBACK,
    )


_PREFERENCE_KEYS = (
    (("ready", "soon", "jaldi", "immediate", "turant"), _readiness_key),
    (("cheap", "affordable", "sasta", "budget-friendly"), lambda p: p.price),
    (("spacious", "big", "large", "family", "bada"), lambda p: -p.bhk),
)


def rerank(candidates: list[Property], preference_text: str | None) -> list[Property]:
    """Stable reorder of the filtered candidates by fuzzy preference."""
    if not candidates:
        return []
    text = (preference_text or "").lower()
    for keywords, key in _PREFERENCE_KEYS:
        if any(keyword in text for keyword in keywords):
            return sorted(candidates, key=key)
    return sorted(candidates, key=lambda p: p.price)


def search(
    properties: tuple[Property, ...],
    criteria: SearchCriteria,
    preference_text: str | None = None,
) -> list[Property]:
    return rerank(hard_filter(properties, criteria), preference_text)
