"""Task 1 done-when: a simulated multi-turn conversation fully populates state."""

from app.agents.qualification import QualificationAgent, next_question
from app.nlu.hybrid import HybridExtractor
from app.state.models import Intent, Stage, Timeline
from app.state.store import SessionStore

WA_ID = "919999000011"


def run_conversation(store: SessionStore, messages: list[str]):
    agent = QualificationAgent(HybridExtractor())
    for text in messages:
        state = store.get_or_create(WA_ID)
        state = agent.process_turn(state, text)
        store.save(state)
    return store.get(WA_ID)


class TestFourMessageConversation:
    MESSAGES = [
        "Hi, I want to buy a flat in Ahmedabad",
        "My budget is under 80 lakh",
        "I prefer Bopal area",
        "Looking for a 3BHK, need it within 6 months",
    ]

    def test_final_state_is_fully_populated(self, tmp_path):
        final = run_conversation(SessionStore(tmp_path / "s.db"), self.MESSAGES)

        assert final.intent == Intent.BUY
        assert final.budget_max == 8_000_000
        assert final.locality == "Bopal"
        assert final.bhk == 3
        assert final.timeline == Timeline.WITHIN_6_MONTHS
        assert final.stage == Stage.QUALIFIED

    def test_stage_progresses_across_turns(self, tmp_path):
        store = SessionStore(tmp_path / "s.db")
        agent = QualificationAgent(HybridExtractor())

        stages = []
        for text in self.MESSAGES:
            state = agent.process_turn(store.get_or_create(WA_ID), text)
            store.save(state)
            stages.append(state.stage)

        assert stages == [
            Stage.QUALIFYING,
            Stage.QUALIFYING,
            Stage.QUALIFYING,
            Stage.QUALIFIED,
        ]

    def test_earlier_fields_survive_later_turns(self, tmp_path):
        store = SessionStore(tmp_path / "s.db")
        run_conversation(store, self.MESSAGES[:2])

        mid = store.get(WA_ID)
        assert mid.intent == Intent.BUY
        assert mid.budget_max == 8_000_000
        assert mid.locality is None  # not stated yet — never guessed


class TestMergeBehaviour:
    def test_customer_can_revise_an_answer(self, tmp_path):
        store = SessionStore(tmp_path / "s.db")
        final = run_conversation(
            store,
            [
                "3BHK in Bopal under 80 lakh, buying",
                "Actually make that a 2BHK",
            ],
        )

        assert final.bhk == 2
        assert final.locality == "Bopal"  # untouched fields survive the revision
        assert final.budget_max == 8_000_000

    def test_uninformative_message_changes_nothing(self, tmp_path):
        store = SessionStore(tmp_path / "s.db")
        final = run_conversation(
            store,
            ["3BHK in Bopal under 80 lakh, buying", "ok thanks"],
        )

        assert final.bhk == 3
        assert final.stage == Stage.QUALIFIED


class TestNextQuestion:
    def test_asks_in_demo_order_budget_then_locality_then_bhk(self, tmp_path):
        store = SessionStore(tmp_path / "s.db")
        agent = QualificationAgent(HybridExtractor())

        state = store.get_or_create(WA_ID)
        state = agent.process_turn(state, "I want to buy a flat in Ahmedabad")
        assert "budget" in next_question(state).lower()

        state = agent.process_turn(state, "under 80 lakh")
        assert "area" in next_question(state).lower()

        state = agent.process_turn(state, "Bopal")
        assert "bedroom" in next_question(state).lower()

        state = agent.process_turn(state, "3BHK")
        assert next_question(state) is None
