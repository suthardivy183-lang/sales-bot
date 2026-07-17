"""Rules-first extraction with an optional LLM pass filling the gaps."""

from app.config import Settings
from app.llm.gemini import GeminiProvider
from app.nlu.llm_extractor import LLMExtractor
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
    if settings.llm_api_key:
        provider = GeminiProvider(
            api_key=settings.llm_api_key, model=settings.llm_model
        )
        return HybridExtractor(LLMExtractor(provider))
    return HybridExtractor()
