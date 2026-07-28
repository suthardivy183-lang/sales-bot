"""Rules-first extraction with an optional LLM pass filling the gaps."""

from app.config import Settings
from app.llm.gemini import GeminiProvider
from app.nlu.llm_extractor import LLMExtractor
from app.nlu.routed_extractor import RoutedLLMExtractor
from app.nlu.routing import ModelRouter, RouteTier
from app.nlu.rules import extract_fields
from app.nlu.schemas import ExtractedFields, merge_preferring
from app.state.models import SessionState


class HybridExtractor:
    """Deterministic rules always run; LLM values never override rule values."""

    def __init__(self, llm_extractor: LLMExtractor | None = None):
        self._llm_extractor = llm_extractor

    def extract(
        self, text: str, state: SessionState | None = None
    ) -> ExtractedFields:
        rule_fields = extract_fields(text)
        if self._llm_extractor is None:
            return rule_fields
        llm_fields = self._llm_extractor.extract(text, state)
        return merge_preferring(rule_fields, llm_fields)


def build_extractor(settings: Settings) -> HybridExtractor:
    if not settings.llm_enabled or not settings.llm_api_key:
        return HybridExtractor()  # rules-only; a stored key never enables calls

    if settings.llm_routing_enabled:
        return HybridExtractor(_build_routed_extractor(settings))

    provider = GeminiProvider(api_key=settings.llm_api_key, model=settings.llm_model)
    return HybridExtractor(LLMExtractor(provider))


def _build_routed_extractor(settings: Settings) -> RoutedLLMExtractor:
    def extractor_for(model: str) -> LLMExtractor:
        return LLMExtractor(
            GeminiProvider(api_key=settings.llm_api_key, model=model)
        )

    return RoutedLLMExtractor(
        router=ModelRouter(
            small_model=settings.llm_model_small,
            large_model=settings.llm_model_large,
        ),
        extractors_by_tier={
            RouteTier.SMALL: extractor_for(settings.llm_model_small),
            RouteTier.LARGE: extractor_for(settings.llm_model_large),
        },
    )
