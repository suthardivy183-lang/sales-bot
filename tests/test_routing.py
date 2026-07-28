"""Task 10 done-when: logs show which model each turn used.

Routing decisions are deterministic (text + rule fields -> tier), so the whole
policy is tested without any API key. The RoutedLLMExtractor is a drop-in for
LLMExtractor: rules-only turns never touch a provider; small and large turns
hit the configured model; every turn logs its tier and model.
"""

import logging

import pytest

from app.config import Settings
from app.nlu.hybrid import HybridExtractor, build_extractor
from app.nlu.routed_extractor import RoutedLLMExtractor
from app.nlu.routing import ModelRouter, RouteDecision, RouteTier
from app.nlu.schemas import ExtractedFields
from app.state.models import Intent

SMALL = "gemini-2.5-flash-lite"
LARGE = "gemini-2.5-flash"


@pytest.fixture
def router() -> ModelRouter:
    return ModelRouter(small_model=SMALL, large_model=LARGE)


class TestRoutingDecisions:
    def test_short_fully_parsed_message_uses_no_model(self, router):
        decision = router.decide("3BHK in Bopal")
        assert decision.tier == RouteTier.RULES_ONLY
        assert decision.model is None

    def test_negotiation_message_escalates_to_large(self, router):
        decision = router.decide("I like #4 but can you get a discount?")
        assert decision.tier == RouteTier.LARGE
        assert decision.model == LARGE

    def test_ambiguity_markers_escalate_to_large(self, router):
        decision = router.decide("not sure which one is better, help?")
        assert decision.tier == RouteTier.LARGE

    def test_long_message_escalates_to_large(self, router):
        long_text = " ".join(["word"] * 30)
        assert router.decide(long_text).tier == RouteTier.LARGE

    def test_short_gap_message_uses_small(self, router):
        # No structured field parses here, but it is short and unambiguous.
        decision = router.decide("something nice please")
        assert decision.tier == RouteTier.SMALL
        assert decision.model == SMALL

    def test_code_switched_intent_cue_uses_small_model(self, router):
        # Hindi purchase intent is parsed, but the rest of the request is open.
        decision = router.decide("मुझे कुछ अच्छा चाहिए")
        assert decision.tier == RouteTier.SMALL

    def test_code_switched_but_parsed_is_not_rules_only(self, router):
        # "2bhk chahiye" parses via rules AND is code-switched -> not free tier.
        decision = router.decide("2bhk chahiye")
        assert decision.tier != RouteTier.RULES_ONLY


class RecordingExtractor:
    def __init__(self, fields: ExtractedFields):
        self._fields = fields
        self.calls = 0

    def extract(self, text, state=None):
        self.calls += 1
        return self._fields


class TestRoutedExtractor:
    def make(self, router):
        small = RecordingExtractor(ExtractedFields(intent=Intent.RENT))
        large = RecordingExtractor(ExtractedFields(intent=Intent.BUY))
        routed = RoutedLLMExtractor(
            router, {RouteTier.SMALL: small, RouteTier.LARGE: large}
        )
        return routed, small, large

    def test_rules_only_turn_calls_no_extractor(self, router):
        routed, small, large = self.make(router)
        result = routed.extract("3BHK in Bopal")
        assert result == ExtractedFields()
        assert small.calls == 0 and large.calls == 0

    def test_small_turn_calls_only_small(self, router):
        routed, small, large = self.make(router)
        routed.extract("something nice please")
        assert small.calls == 1 and large.calls == 0

    def test_large_turn_calls_only_large(self, router):
        routed, small, large = self.make(router)
        routed.extract("not sure which one, but maybe a discount?")
        assert large.calls == 1 and small.calls == 0

    def test_each_turn_logs_its_model(self, router, caplog):
        routed, _, _ = self.make(router)
        with caplog.at_level(logging.INFO):
            routed.extract("3BHK in Bopal")          # rules_only
            routed.extract("not sure, can you discount?")  # large
        messages = [r.message for r in caplog.records if "Model routing" in r.message]
        assert any("tier=rules_only" in m and "model=none" in m for m in messages)
        assert any(f"tier=large" in m and f"model={LARGE}" in m for m in messages)


class TestBuildExtractor:
    def test_key_without_explicit_enable_stays_rules_only(self):
        settings = Settings(llm_api_key="k", llm_routing_enabled=True, _env_file=None)
        extractor = build_extractor(settings)
        assert extractor._llm_extractor is None

    def test_enabled_routing_disabled_uses_single_model(self):
        settings = Settings(
            llm_api_key="k", llm_enabled=True, llm_routing_enabled=False, _env_file=None
        )
        extractor = build_extractor(settings)
        assert isinstance(extractor, HybridExtractor)
        assert not isinstance(extractor._llm_extractor, RoutedLLMExtractor)

    def test_enabled_routing_builds_routed_extractor(self):
        settings = Settings(
            llm_api_key="k", llm_enabled=True, llm_routing_enabled=True, _env_file=None
        )
        extractor = build_extractor(settings)
        assert isinstance(extractor._llm_extractor, RoutedLLMExtractor)

    def test_no_key_stays_rules_only_even_with_routing_flag(self):
        settings = Settings(
            llm_api_key="", llm_enabled=True, llm_routing_enabled=True, _env_file=None
        )
        extractor = build_extractor(settings)
        assert extractor._llm_extractor is None
