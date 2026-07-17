"""Task 6 done-when: the full Ahmedabad scenario runs end to end, unassisted,
including the trap question — all through the webhook."""

import pytest
from fastapi.testclient import TestClient

from app.actions.crm import SqliteCrmBackend
from app.config import get_settings
from app.main import create_app
from app.state.store import SessionStore
from tests.conftest import make_test_settings, make_whatsapp_payload

WA_ID = "919999000011"


@pytest.fixture
def env(tmp_path):
    settings = make_test_settings(tmp_path)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), settings


def send(client: TestClient, text: str, message_id: str, wa_id: str = WA_ID) -> str:
    response = client.post(
        "/webhook",
        json=make_whatsapp_payload(text=text, wa_id=wa_id, message_id=message_id),
    )
    assert response.status_code == 200
    return response.json()["replies"][0]["reply"]


class TestFullAhmedabadScenario:
    def test_complete_demo_flow(self, env):
        client, settings = env

        # 1. Greeting with intent -> asks for budget.
        reply = send(client, "Hi, I'm looking to buy a flat in Ahmedabad", "wamid.1")
        assert "budget" in reply.lower()

        # 2. Budget -> asks for area.
        reply = send(client, "Under 90 lakh", "wamid.2")
        assert "area" in reply.lower()

        # 3. Locality -> asks for bedrooms.
        reply = send(client, "Bopal side", "wamid.3")
        assert "bedroom" in reply.lower()

        # 4. BHK + timeline -> qualified, verified match presented.
        reply = send(client, "3BHK please, ready to move", "wamid.4")
        assert "3BHK in Bopal" in reply
        assert "₹85 lakh" in reply
        assert "property #4" in reply
        assert "book a viewing" in reply.lower()

        # 5. EMI on the matched property — deterministic, assumption-stated.
        reply = send(client, "What would the EMI be?", "wamid.5")
        assert "₹59,012/month" in reply
        assert "8.5%" in reply and "20 years" in reply

        # 6. THE TRAP: unverifiable amenity on the Shela property -> refused.
        reply = send(client, "Does the Shela property have a private pool?", "wamid.6")
        assert "can't confirm" in reply
        assert "private pool" in reply
        assert "yes" not in reply.lower()

        # 7. Booking -> slot confirmed, CRM outcome written.
        reply = send(client, "Great, book a viewing", "wamid.7")
        assert "booked" in reply.lower()
        assert "Saturday 11:00" in reply
        assert "3BHK" in reply and "Bopal" in reply

        # 8. Webhook replay of the booking message -> same slot, no duplicates.
        replay = send(client, "Great, book a viewing", "wamid.7")
        assert "Saturday 11:00" in replay

        # --- Post-conditions: state, CRM, and booking are all consistent. ---
        state = SessionStore(settings.database_path).get(WA_ID)
        assert state.stage == "booked"
        assert state.selected_property_id == 4
        assert state.budget_max == 9_000_000

        leads = SqliteCrmBackend(settings.database_path).all_leads()
        notes = [lead.note for lead in leads]
        assert len(leads) == 3  # match presented, trap handoff, booking — no dupes
        assert any("presented properties [4]" in note for note in notes)
        assert any(note.startswith("HANDOFF") for note in notes)
        assert any("viewing booked: Saturday 11:00" in note for note in notes)
        assert all(lead.wa_id_masked.startswith("*") for lead in leads)


class TestOrchestratorEdges:
    def test_no_match_is_reported_honestly(self, env):
        client, settings = env
        send(client, "I want to buy a flat", "wamid.a")
        send(client, "under 80 lakh", "wamid.b")
        send(client, "Bopal", "wamid.c")
        reply = send(client, "3BHK", "wamid.d")

        # 3BHK in Bopal costs ₹85 lakh — over budget. No fudged match.
        assert "don't have a verified listing" in reply
        leads = SqliteCrmBackend(settings.database_path).all_leads()
        assert any("no verified match" in lead.note for lead in leads)

    def test_revised_preference_reruns_the_search(self, env):
        client, _ = env
        send(client, "buying a flat, 3BHK in Bopal, under 90 lakh", "wamid.a")
        reply = send(client, "actually make it a 2BHK", "wamid.b")

        assert "2BHK in Bopal" in reply
        assert "property #1" in reply

    def test_booking_before_any_match_falls_back_to_qualification(self, env):
        client, _ = env
        reply = send(client, "book a site visit", "wamid.a")
        # No target property exists yet — the bot keeps qualifying instead.
        assert "?" in reply

    def test_sessions_do_not_leak_across_numbers(self, env):
        client, _ = env
        send(client, "buying a flat, 3BHK in Bopal, under 90 lakh", "wamid.a")
        reply = send(
            client, "Hi, I want to buy a flat", "wamid.b", wa_id="918888000022"
        )
        assert "budget" in reply.lower()  # fresh lead starts from scratch
