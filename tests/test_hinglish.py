"""Task 7 done-when: mixed-language phrasing still extracts and filters correctly."""

import pytest

from app.nlu.hinglish import is_code_switched
from app.nlu.rules import extract_fields
from app.properties.repository import PropertyRepository
from app.state.models import Intent, Timeline
from app.tools.property_search import SearchCriteria, search
from tests.conftest import make_whatsapp_payload


class TestDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "70 lakh tak ka budget hai",
            "Bopal mein 2BHK chahiye",
            "ghar dekhna hai",
            "kitna hai price?",
            "मुझे फ्लैट चाहिए",  # Devanagari script
        ],
    )
    def test_code_switched_input_is_detected(self, text):
        assert is_code_switched(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "I want a flat in Bopal",
            "under 80 lakh",
            "What would the EMI be?",
            "book a viewing",
        ],
    )
    def test_plain_english_is_not_flagged(self, text):
        assert is_code_switched(text) is False


class TestHinglishExtraction:
    BUDGET_CASES = [
        ("70 lakh tak ka budget hai", None, 7_000_000),
        ("80 lakh ke andar chahiye", None, 8_000_000),
        ("1 cr se kam", None, 10_000_000),
        ("90 lakh ke aas paas", None, 9_000_000),
        ("50 lakh se upar wala", 5_000_000, None),
        ("60 se 80 lakh ke beech", 6_000_000, 8_000_000),
    ]

    @pytest.mark.parametrize(("text", "expected_min", "expected_max"), BUDGET_CASES)
    def test_budget_phrasings(self, text, expected_min, expected_max):
        fields = extract_fields(text)
        assert fields.budget_min == expected_min
        assert fields.budget_max == expected_max

    @pytest.mark.parametrize(
        ("text", "expected_bhk"),
        [("2 bhk chahiye", 2), ("3 kamre ka flat", 3), ("teen nahi, 2 kamron wala", 2)],
    )
    def test_bhk_phrasings(self, text, expected_bhk):
        assert extract_fields(text).bhk == expected_bhk

    @pytest.mark.parametrize(
        ("text", "expected_intent"),
        [
            ("ghar lena hai", Intent.BUY),
            ("makaan chahiye Bopal mein", Intent.BUY),
            ("flat khareedna hai", Intent.BUY),
            ("kiraye pe chahiye", Intent.RENT),
        ],
    )
    def test_intent_phrasings(self, text, expected_intent):
        assert extract_fields(text).intent == expected_intent

    @pytest.mark.parametrize(
        ("text", "expected_timeline"),
        [
            ("turant chahiye", Timeline.IMMEDIATE),
            ("abhi shift hona hai", Timeline.IMMEDIATE),
            ("2 mahine mein chahiye", Timeline.WITHIN_3_MONTHS),
            ("agle mahine tak", Timeline.WITHIN_3_MONTHS),
        ],
    )
    def test_timeline_phrasings(self, text, expected_timeline):
        assert extract_fields(text).timeline == expected_timeline


class TestDoneWhen:
    def test_hinglish_budget_phrase_extracts_and_filters_correctly(self):
        fields = extract_fields("Bopal mein 2BHK chahiye, budget 70 lakh tak hai")

        assert fields.intent == Intent.BUY
        assert fields.bhk == 2
        assert fields.locality == "Bopal"
        assert fields.budget_max == 7_000_000

        results = search(
            PropertyRepository().all(),
            SearchCriteria(
                bhk=fields.bhk,
                locality=fields.locality,
                budget_max=fields.budget_max,
            ),
        )
        assert [prop.id for prop in results] == [1]


class TestHinglishConversationEndToEnd:
    def test_full_hinglish_flow_reaches_a_verified_match(self, client):
        def send(text, message_id):
            response = client.post(
                "/webhook",
                json=make_whatsapp_payload(text=text, message_id=message_id),
            )
            return response.json()["replies"][0]["reply"]

        reply = send("Ahmedabad mein flat lena hai", "wamid.h1")
        assert "budget" in reply.lower()

        reply = send("70 lakh tak", "wamid.h2")
        assert "area" in reply.lower()

        reply = send("Bopal mein", "wamid.h3")
        assert "bedroom" in reply.lower()

        reply = send("2 bhk chahiye, turant", "wamid.h4")
        assert "2BHK in Bopal" in reply
        assert "₹65 lakh" in reply
        assert "property #1" in reply
