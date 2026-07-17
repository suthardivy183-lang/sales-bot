"""Task 5 done-when: replaying the same incoming message twice produces exactly
one CRM row and one booking, never two."""

import httpx
import pytest

from app.actions.booking import BookingTool
from app.actions.crm import (
    CrmTool,
    SheetsCrmBackend,
    SqliteCrmBackend,
    lead_from_state,
)
from app.actions.ledger import ActionLedger
from app.actions.models import CrmError, SlotUnavailableError
from app.state.models import Intent, SessionState, Stage

WA_ID = "919999000011"
MESSAGE_ID = "wamid.BOOK-0001"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "sales.db"


@pytest.fixture
def ledger(db_path):
    return ActionLedger(db_path)


@pytest.fixture
def state():
    return SessionState(
        session_id="sess-1",
        wa_id=WA_ID,
        intent=Intent.BUY,
        locality="Bopal",
        budget_max=9_000_000,
        bhk=3,
        stage=Stage.QUALIFIED,
        selected_property_id=4,
    )


class TestCrmIdempotency:
    def test_replayed_message_writes_exactly_one_row(self, db_path, ledger, state):
        backend = SqliteCrmBackend(db_path)
        tool = CrmTool(backend, ledger)

        first = tool.write_lead(MESSAGE_ID, state, note="booked viewing")
        replay = tool.write_lead(MESSAGE_ID, state, note="booked viewing")

        assert first.created is True
        assert replay.created is False
        assert replay.lead == first.lead
        assert len(backend.all_leads()) == 1

    def test_distinct_messages_write_distinct_rows(self, db_path, ledger, state):
        backend = SqliteCrmBackend(db_path)
        tool = CrmTool(backend, ledger)

        tool.write_lead("wamid.A", state)
        tool.write_lead("wamid.B", state)

        assert len(backend.all_leads()) == 2

    def test_crm_row_never_contains_full_phone_number(self, db_path, ledger, state):
        backend = SqliteCrmBackend(db_path)
        CrmTool(backend, ledger).write_lead(MESSAGE_ID, state)

        (lead,) = backend.all_leads()
        assert WA_ID not in lead.model_dump_json()
        assert lead.wa_id_masked.endswith("0011")
        assert lead.wa_id_masked.startswith("*")

    def test_lead_captures_the_qualified_state(self, state):
        lead = lead_from_state(state, note="n", property_id=4)
        assert lead.intent == "buy"
        assert lead.locality == "Bopal"
        assert lead.budget_max == 9_000_000
        assert lead.bhk == 3
        assert lead.stage == "qualified"
        assert lead.property_id == 4


class TestBookingIdempotency:
    def test_replayed_message_books_exactly_one_slot(self, db_path, ledger):
        tool = BookingTool(db_path, ledger)

        first = tool.book(MESSAGE_ID, WA_ID)
        replay = tool.book(MESSAGE_ID, WA_ID)

        assert first.created is True
        assert replay.created is False
        assert replay.slot_id == first.slot_id
        assert len(tool.available_slots()) == 3  # one slot consumed, not two

    def test_distinct_messages_take_distinct_slots(self, db_path, ledger):
        tool = BookingTool(db_path, ledger)

        first = tool.book("wamid.A", WA_ID)
        second = tool.book("wamid.B", "918888000022")

        assert first.slot_id != second.slot_id
        assert len(tool.available_slots()) == 2

    def test_requested_slot_already_taken_raises(self, db_path, ledger):
        tool = BookingTool(db_path, ledger)
        taken = tool.book("wamid.A", WA_ID).slot_id

        with pytest.raises(SlotUnavailableError):
            tool.book("wamid.B", "918888000022", slot_id=taken)

    def test_exhausted_slots_raise_not_double_book(self, db_path, ledger):
        tool = BookingTool(db_path, ledger)
        for i in range(4):
            tool.book(f"wamid.{i}", f"91900000001{i}")

        assert tool.available_slots() == []
        with pytest.raises(SlotUnavailableError):
            tool.book("wamid.overflow", "919999999999")

    def test_booking_stores_masked_number_only(self, db_path, ledger):
        result = BookingTool(db_path, ledger).book(MESSAGE_ID, WA_ID)
        assert WA_ID not in result.model_dump_json()


class TestSheetsBackend:
    def make_backend(self, handler):
        seen: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        backend = SheetsCrmBackend(
            spreadsheet_id="SHEET123",
            token_supplier=lambda: "ya29.test-token",
            client=httpx.Client(transport=httpx.MockTransport(recording)),
        )
        return backend, seen

    def test_appends_lead_row_with_bearer_token(self, state):
        backend, seen = self.make_backend(
            lambda request: httpx.Response(200, json={"updates": {}})
        )
        backend.append_lead(lead_from_state(state))

        request = seen[0]
        assert "SHEET123" in str(request.url)
        assert "values" in str(request.url)
        assert request.headers["Authorization"] == "Bearer ya29.test-token"

    def test_api_error_raises_crm_error(self, state):
        backend, _ = self.make_backend(
            lambda request: httpx.Response(403, json={"error": "denied"})
        )
        with pytest.raises(CrmError, match="403"):
            backend.append_lead(lead_from_state(state))

    def test_ledger_prevents_double_append_on_replay(self, ledger, state):
        calls = []
        backend, _ = self.make_backend(
            lambda request: (calls.append(1), httpx.Response(200, json={}))[1]
        )
        tool = CrmTool(backend, ledger)

        tool.write_lead(MESSAGE_ID, state)
        tool.write_lead(MESSAGE_ID, state)

        assert len(calls) == 1  # the replay never reached the Sheets API
