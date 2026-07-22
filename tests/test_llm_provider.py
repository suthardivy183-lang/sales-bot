"""Gemini provider (mocked transport — no real API calls) and LLM extractor."""

import json

import httpx
import pytest

from app.llm.gemini import GeminiProvider
from app.llm.provider import LLMProviderError
from app.nlu.hybrid import HybridExtractor
from app.nlu.llm_extractor import LLMExtractor
from app.nlu.schemas import ExtractedFields, merge_preferring
from app.state.models import Intent, Timeline


def gemini_response(payload: dict) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(payload)}]}}
        ]
    }


def make_provider(handler) -> tuple[GeminiProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(recording_handler))
    return GeminiProvider(api_key="test-key", client=client), seen


class TestGeminiProvider:
    def test_parses_json_from_first_candidate(self):
        provider, _ = make_provider(
            lambda request: httpx.Response(200, json=gemini_response({"bhk": 3}))
        )
        assert provider.generate_json(system="s", user="u") == {"bhk": 3}

    def test_api_key_travels_in_header_never_in_url(self):
        provider, seen = make_provider(
            lambda request: httpx.Response(200, json=gemini_response({}))
        )
        provider.generate_json(system="s", user="u")

        request = seen[0]
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)

    def test_requests_json_mode_at_temperature_zero(self):
        provider, seen = make_provider(
            lambda request: httpx.Response(200, json=gemini_response({}))
        )
        provider.generate_json(system="s", user="u")

        body = json.loads(seen[0].content)
        assert body["generationConfig"]["response_mime_type"] == "application/json"
        assert body["generationConfig"]["temperature"] == 0

    def test_non_200_raises_provider_error(self):
        provider, _ = make_provider(
            lambda request: httpx.Response(429, json={"error": "quota"})
        )
        with pytest.raises(LLMProviderError, match="429"):
            provider.generate_json(system="s", user="u")

    def test_malformed_body_raises_provider_error(self):
        provider, _ = make_provider(
            lambda request: httpx.Response(200, json={"candidates": []})
        )
        with pytest.raises(LLMProviderError):
            provider.generate_json(system="s", user="u")


class FakeProvider:
    def __init__(self, data: dict | Exception):
        self._data = data

    def generate_json(self, *, system: str, user: str) -> dict:
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class TestLLMExtractor:
    def test_valid_payload_becomes_extracted_fields(self):
        extractor = LLMExtractor(
            FakeProvider(
                {
                    "intent": "buy",
                    "locality": "bopal",
                    "budget_max": 8000000,
                    "bhk": 3,
                    "timeline": "within_6_months",
                }
            )
        )
        fields = extractor.extract("some hinglish message")

        assert fields.intent == Intent.BUY
        assert fields.locality == "Bopal"  # canonicalized to fixture name
        assert fields.budget_max == 8_000_000
        assert fields.bhk == 3
        assert fields.timeline == Timeline.WITHIN_6_MONTHS

    def test_unknown_locality_is_kept_for_honest_no_match(self):
        extractor = LLMExtractor(FakeProvider({"locality": "Naranpura"}))
        assert extractor.extract("flat in naranpura").locality == "Naranpura"

    def test_invalid_values_become_none_not_errors(self):
        extractor = LLMExtractor(
            FakeProvider(
                {"intent": "browse", "bhk": "three", "timeline": "someday",
                 "budget_max": -5, "locality": ""}
            )
        )
        assert extractor.extract("whatever") == ExtractedFields()

    def test_provider_failure_degrades_to_empty_extraction(self):
        extractor = LLMExtractor(FakeProvider(LLMProviderError("down")))
        assert extractor.extract("anything") == ExtractedFields()


class TestHybridExtractor:
    def test_rule_values_always_beat_llm_values(self):
        llm = LLMExtractor(FakeProvider({"bhk": 4, "budget_max": 1}))
        fields = HybridExtractor(llm).extract("3BHK under 80 lakh")

        assert fields.bhk == 3
        assert fields.budget_max == 8_000_000

    def test_llm_fills_fields_rules_could_not_parse(self):
        llm = LLMExtractor(FakeProvider({"timeline": "immediate"}))
        fields = HybridExtractor(llm).extract("3BHK, want to shift as soon as school year ends")

        assert fields.bhk == 3
        assert fields.timeline == Timeline.IMMEDIATE

    def test_provider_failure_preserves_rule_derived_fields(self):
        llm = LLMExtractor(FakeProvider(LLMProviderError("service unavailable")))

        fields = HybridExtractor(llm).extract("3BHK in Bopal under 80 lakh")

        assert fields.bhk == 3
        assert fields.locality == "Bopal"
        assert fields.budget_max == 8_000_000

    def test_llm_can_fill_devanagari_turn_without_overriding_rules(self):
        llm = LLMExtractor(
            FakeProvider(
                {
                    "intent": "buy",
                    "locality": "Bopal",
                    "budget_max": 8_000_000,
                    "bhk": 3,
                    "timeline": "within_6_months",
                }
            )
        )

        fields = HybridExtractor(llm).extract("मुझे बोपल में घर चाहिए")

        assert fields.intent == Intent.BUY
        assert fields.locality == "Bopal"
        assert fields.budget_max == 8_000_000
        assert fields.bhk == 3
        assert fields.timeline == Timeline.WITHIN_6_MONTHS

    def test_merge_preferring_is_field_wise(self):
        primary = ExtractedFields(bhk=2)
        secondary = ExtractedFields(bhk=4, locality="Shela")

        merged = merge_preferring(primary, secondary)
        assert merged.bhk == 2
        assert merged.locality == "Shela"
