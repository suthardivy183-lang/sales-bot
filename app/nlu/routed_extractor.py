"""A routing LLM extractor: same interface as LLMExtractor, but picks a model
tier per turn and logs which one ran (Task 10 done-when).

Because it exposes the identical `.extract(text, state)` method, it drops into
HybridExtractor with no change to the extractor or any existing test.
"""

import logging

from app.nlu.routing import ModelRouter, RouteTier
from app.nlu.rules import extract_fields
from app.nlu.llm_extractor import LLMExtractor
from app.nlu.schemas import ExtractedFields
from app.state.models import SessionState

logger = logging.getLogger(__name__)


class RoutedLLMExtractor:
    def __init__(
        self,
        router: ModelRouter,
        extractors_by_tier: dict[RouteTier, LLMExtractor],
    ):
        self._router = router
        self._extractors = extractors_by_tier

    def extract(
        self, text: str, state: SessionState | None = None
    ) -> ExtractedFields:
        rule_fields = extract_fields(text)
        decision = self._router.decide(text, rule_fields)
        logger.info(
            "Model routing: tier=%s model=%s (%s)",
            decision.tier.value,
            decision.model or "none",
            decision.reason,
        )

        if decision.tier == RouteTier.RULES_ONLY:
            # No LLM call — HybridExtractor merges rules over this empty result.
            return ExtractedFields()

        extractor = self._extractors.get(decision.tier)
        if extractor is None:  # defensive: unconfigured tier degrades to rules
            logger.warning("No extractor for tier %s; using rules only", decision.tier)
            return ExtractedFields()
        return extractor.extract(text, state)
