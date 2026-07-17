"""Table-driven tests for the deterministic extractor (engineering rule 4)."""

import pytest

from app.nlu.rules import extract_fields
from app.state.models import Intent, Timeline

BUDGET_CASES = [
    ("My budget is under 80 lakh", None, 8_000_000),
    ("under 1.2 cr", None, 12_000_000),
    ("upto 95 lakhs", None, 9_500_000),
    ("less than 70 lac", None, 7_000_000),
    ("between 60 and 80 lakh", 6_000_000, 8_000_000),
    ("60-80 lakh", 6_000_000, 8_000_000),
    ("60 to 80 lakhs works for us", 6_000_000, 8_000_000),
    ("above 50 lakh only", 5_000_000, None),
    ("at least 1 crore", 10_000_000, None),
    ("₹65,00,000", None, 6_500_000),
    ("70L", None, 7_000_000),
    ("budget 85 lakh", None, 8_500_000),
    ("70 lakh tak ka budget hai", None, 7_000_000),  # Hinglish ceiling
    ("50 lakh se upar", 5_000_000, None),  # Hinglish floor
    ("hello there", None, None),
    ("I want a 3 bhk", None, None),  # BHK digit must not parse as money
]


@pytest.mark.parametrize(("text", "expected_min", "expected_max"), BUDGET_CASES)
def test_budget_extraction(text, expected_min, expected_max):
    fields = extract_fields(text)
    assert fields.budget_min == expected_min
    assert fields.budget_max == expected_max


BHK_CASES = [
    ("3BHK", 3),
    ("3 bhk", 3),
    ("a 2-bhk please", 2),
    ("three bhk", 3),
    ("4 bedroom house", 4),
    ("2 or 3 bhk", 3),
    ("no bedrooms mentioned", None),
]


@pytest.mark.parametrize(("text", "expected"), BHK_CASES)
def test_bhk_extraction(text, expected):
    assert extract_fields(text).bhk == expected


LOCALITY_CASES = [
    ("I prefer Bopal area", "Bopal"),
    ("something in shela", "Shela"),
    ("Satellite would be great", "Satellite"),
    ("near SG Highway", "SG Highway"),
    ("on S.G. Highway", "SG Highway"),
    ("I want a flat in Ahmedabad", None),  # city, not a locality
]


@pytest.mark.parametrize(("text", "expected"), LOCALITY_CASES)
def test_locality_extraction(text, expected):
    assert extract_fields(text).locality == expected


INTENT_CASES = [
    ("I want to buy a flat", Intent.BUY),
    ("looking for an apartment", Intent.BUY),
    ("2bhk chahiye", Intent.BUY),  # Hinglish
    ("flat on rent please", Intent.RENT),
    ("kiraya kitna hai", Intent.RENT),
    ("hello", None),
]


@pytest.mark.parametrize(("text", "expected"), INTENT_CASES)
def test_intent_extraction(text, expected):
    assert extract_fields(text).intent == expected


TIMELINE_CASES = [
    ("need it immediately", Timeline.IMMEDIATE),
    ("asap please", Timeline.IMMEDIATE),
    ("ready to move", Timeline.IMMEDIATE),
    ("within 2 months", Timeline.WITHIN_3_MONTHS),
    ("next month ideally", Timeline.WITHIN_3_MONTHS),
    ("within 6 months", Timeline.WITHIN_6_MONTHS),
    ("in 8 months or so", Timeline.WITHIN_12_MONTHS),
    ("next year", Timeline.WITHIN_12_MONTHS),
    ("no timeline here", None),
]


@pytest.mark.parametrize(("text", "expected"), TIMELINE_CASES)
def test_timeline_extraction(text, expected):
    assert extract_fields(text).timeline == expected


def test_timeline_months_never_parse_as_budget():
    fields = extract_fields("within 6 months")
    assert fields.budget_max is None
    assert fields.timeline == Timeline.WITHIN_6_MONTHS


def test_combined_message_extracts_every_field():
    fields = extract_fields(
        "Looking to buy a 3BHK in Bopal, between 60 and 85 lakh, within 6 months"
    )
    assert fields.intent == Intent.BUY
    assert fields.bhk == 3
    assert fields.locality == "Bopal"
    assert fields.budget_min == 6_000_000
    assert fields.budget_max == 8_500_000
    assert fields.timeline == Timeline.WITHIN_6_MONTHS
