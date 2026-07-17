"""Task 2 done-when: '2BHK in Bopal under 70 lakh' returns exactly property #1."""

import pytest

from app.nlu.rules import extract_fields
from app.properties.models import PossessionStatus
from app.properties.repository import PropertyRepository
from app.state.models import SessionState, Timeline
from app.tools.property_search import (
    SearchCriteria,
    criteria_from_state,
    hard_filter,
    rerank,
    search,
)


@pytest.fixture(scope="module")
def repo() -> PropertyRepository:
    return PropertyRepository()


def ids(properties) -> list[int]:
    return [prop.id for prop in properties]


class TestFixtures:
    def test_all_five_fixtures_load(self, repo):
        assert ids(repo.all()) == [1, 2, 3, 4, 5]

    def test_get_by_id(self, repo):
        assert repo.get(2).locality == "Shela"
        assert repo.get(99) is None

    def test_no_fixture_has_a_private_pool_field(self, repo):
        # The trap question (Task 4) depends on this staying true.
        assert all("private_pool" not in prop.model_fields_set for prop in repo.all())
        assert "private_pool" not in type(repo.all()[0]).model_fields


class TestDoneWhen:
    def test_2bhk_bopal_under_70_lakh_returns_exactly_property_1(self, repo):
        fields = extract_fields("2BHK in Bopal under 70 lakh")
        criteria = SearchCriteria(
            bhk=fields.bhk, locality=fields.locality, budget_max=fields.budget_max
        )

        assert ids(search(repo.all(), criteria)) == [1]


class TestHardFilter:
    @pytest.mark.parametrize(
        ("criteria", "expected_ids"),
        [
            (SearchCriteria(bhk=3, locality="Bopal"), [4]),
            (SearchCriteria(locality="Bopal"), [1, 4]),
            (SearchCriteria(bhk=3, budget_max=10_000_000), [2, 4]),
            (SearchCriteria(bhk=2, locality="Shela"), []),
            (SearchCriteria(bhk=3, locality="Bopal", budget_max=8_000_000), []),
            (SearchCriteria(bhk=3, status=PossessionStatus.READY_TO_MOVE), [4]),
            (SearchCriteria(), [1, 2, 3, 4, 5]),
            (SearchCriteria(locality="sg highway"), [5]),  # alias-normalized
        ],
    )
    def test_filter_combinations(self, repo, criteria, expected_ids):
        assert ids(hard_filter(repo.all(), criteria)) == expected_ids

    def test_unknown_locality_returns_no_match_not_everything(self, repo):
        assert hard_filter(repo.all(), SearchCriteria(locality="Naranpura")) == []


class TestRerank:
    def test_ready_soon_puts_ready_to_move_first(self, repo):
        three_bhks = hard_filter(repo.all(), SearchCriteria(bhk=3))
        assert ids(rerank(three_bhks, "we want something ready soon")) == [4, 2]

    def test_family_preference_puts_bigger_homes_first(self, repo):
        bopal = hard_filter(repo.all(), SearchCriteria(locality="Bopal"))
        assert ids(rerank(bopal, "family-friendly please")) == [4, 1]

    def test_affordable_preference_sorts_by_price(self, repo):
        everything = list(repo.all())
        assert ids(rerank(everything, "sasta chahiye"))[:2] == [1, 4]

    def test_rerank_never_adds_or_removes_candidates(self, repo):
        filtered = hard_filter(repo.all(), SearchCriteria(bhk=3))
        reranked = rerank(filtered, "spacious and ready and affordable")

        assert sorted(ids(reranked)) == sorted(ids(filtered))
        assert rerank([], "anything") == []

    def test_no_preference_gives_stable_price_order(self, repo):
        assert ids(search(repo.all(), SearchCriteria(locality="Bopal"))) == [1, 4]


class TestCriteriaFromState:
    def test_maps_qualified_state_onto_hard_filters(self):
        state = SessionState(
            session_id="s1",
            wa_id="919999000011",
            bhk=2,
            locality="Bopal",
            budget_max=7_000_000,
        )
        criteria = criteria_from_state(state)

        assert criteria == SearchCriteria(
            bhk=2, locality="Bopal", budget_max=7_000_000, status=None
        )

    def test_immediate_timeline_requires_ready_to_move(self, repo):
        state = SessionState(
            session_id="s1",
            wa_id="919999000011",
            bhk=3,
            timeline=Timeline.IMMEDIATE,
        )
        results = search(repo.all(), criteria_from_state(state))

        assert ids(results) == [4]  # under-construction Shela flat excluded
