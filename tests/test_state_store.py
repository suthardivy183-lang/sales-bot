from app.state.models import Intent, SessionState, Stage, Timeline
from app.state.store import SessionStore


def make_store(tmp_path) -> SessionStore:
    return SessionStore(tmp_path / "sessions.db")


class TestSessionStore:
    def test_get_returns_none_for_unknown_number(self, tmp_path):
        assert make_store(tmp_path).get("919999000011") is None

    def test_get_or_create_creates_fresh_session(self, tmp_path):
        store = make_store(tmp_path)
        state = store.get_or_create("919999000011")

        assert state.wa_id == "919999000011"
        assert state.stage == Stage.NEW
        assert state.session_id

    def test_get_or_create_is_stable_across_calls(self, tmp_path):
        store = make_store(tmp_path)
        first = store.get_or_create("919999000011")
        second = store.get_or_create("919999000011")

        assert first.session_id == second.session_id

    def test_save_round_trips_all_fields(self, tmp_path):
        store = make_store(tmp_path)
        state = store.get_or_create("919999000011").model_copy(
            update={
                "intent": Intent.BUY,
                "locality": "Bopal",
                "budget_min": 6_000_000,
                "budget_max": 8_000_000,
                "bhk": 3,
                "timeline": Timeline.WITHIN_6_MONTHS,
                "selected_property_id": 4,
                "stage": Stage.QUALIFIED,
            }
        )
        store.save(state)

        loaded = store.get("919999000011")
        assert loaded == state

    def test_sessions_are_isolated_per_number(self, tmp_path):
        store = make_store(tmp_path)
        first = store.get_or_create("919999000011")
        store.save(first.model_copy(update={"bhk": 3}))
        second = store.get_or_create("918888000022")

        assert second.bhk is None
        assert first.session_id != second.session_id

    def test_state_survives_store_restart(self, tmp_path):
        db_path = tmp_path / "sessions.db"
        SessionStore(db_path).save(
            SessionState(session_id="abc123", wa_id="919999000011", bhk=2)
        )

        reopened = SessionStore(db_path).get("919999000011")
        assert reopened is not None
        assert reopened.bhk == 2
