"""V1: ElevenLabs voice turns reuse the existing sales orchestrator."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_elevenlabs_payload(
    transcript: str = "I want a flat in Ahmedabad",
    caller_phone_number: str = "919999000011",
    event_id: str = "elevenlabs-turn-0001",
) -> dict:
    """Mocked normalized payload sent by the ElevenLabs webhook tool."""
    return {
        "caller_phone_number": caller_phone_number,
        "event_id": event_id,
        "transcript": transcript,
        "timestamp": "2026-07-18T10:30:00Z",
    }


class TestElevenLabsVoiceWebhook:
    def test_transcript_uses_existing_orchestrator_and_caller_session(
        self, client
    ):
        caller_phone_number = "919999000011"

        first = client.post(
            "/voice/elevenlabs/webhook",
            json=make_elevenlabs_payload(caller_phone_number=caller_phone_number),
        )
        second = client.post(
            "/voice/elevenlabs/webhook",
            json=make_elevenlabs_payload(
                transcript="Under 70 lakh",
                caller_phone_number=caller_phone_number,
                event_id="elevenlabs-turn-0002",
            ),
        )

        assert first.status_code == 200
        assert "budget" in first.json()["reply"].lower()
        assert second.status_code == 200
        assert "area" in second.json()["reply"].lower()

    def test_browser_preview_without_a_phone_number_keeps_turn_state(self, client):
        first = client.post(
            "/voice/elevenlabs/webhook",
            json=make_elevenlabs_payload(
                caller_phone_number="",
                event_id="preview-conversation-7:1",
                transcript="I want a flat in Ahmedabad",
            ),
        )
        second = client.post(
            "/voice/elevenlabs/webhook",
            json=make_elevenlabs_payload(
                caller_phone_number="",
                event_id="preview-conversation-7:2",
                transcript="Under 70 lakh",
            ),
        )

        assert first.status_code == 200
        assert "budget" in first.json()["reply"].lower()
        assert second.status_code == 200
        assert "area" in second.json()["reply"].lower()

    def test_replayed_voice_event_returns_cached_reply_without_double_booking(self, client):
        caller_phone_number = "919999000011"
        for event_id, transcript in (
            ("voice-1", "I want a flat in Ahmedabad"),
            ("voice-2", "Under 90 lakh"),
            ("voice-3", "Bopal"),
            ("voice-4", "3BHK, ready to move"),
        ):
            client.post(
                "/voice/elevenlabs/webhook",
                json=make_elevenlabs_payload(
                    transcript=transcript,
                    caller_phone_number=caller_phone_number,
                    event_id=event_id,
                ),
            )

        booking = make_elevenlabs_payload(
            transcript="book a viewing",
            caller_phone_number=caller_phone_number,
            event_id="voice-booking",
        )
        first = client.post("/voice/elevenlabs/webhook", json=booking)
        replay = client.post("/voice/elevenlabs/webhook", json=booking)

        assert first.json() == replay.json()
        assert len(client.app.state.orchestrator._booking.available_slots()) == 3

    def test_spoken_hinglish_transcript_reaches_a_verified_match(self, client):
        caller_phone_number = "918888000022"
        messages = (
            ("spoken-1", "Mujhe Ahmedabad mein flat chahiye"),
            ("spoken-2", "sattar lakh tak"),
            ("spoken-3", "Bopaal mein"),
            ("spoken-4", "do BHK, teen mahine mein"),
        )
        replies = []
        for event_id, transcript in messages:
            response = client.post(
                "/voice/elevenlabs/webhook",
                json=make_elevenlabs_payload(
                    transcript=transcript,
                    caller_phone_number=caller_phone_number,
                    event_id=event_id,
                ),
            )
            replies.append(response.json()["reply"])

        assert "2BHK in Bopal" in replies[-1]
        assert "₹65 lakh" in replies[-1]

    def test_difficult_voice_turn_is_handed_to_a_human(self, client):
        response = client.post(
            "/voice/elevenlabs/webhook",
            json=make_elevenlabs_payload(
                transcript="Can I talk to a human agent?",
                event_id="voice-human-handoff",
            ),
        )

        assert response.status_code == 200
        assert "human sales agent" in response.json()["reply"].lower()

    def test_rejects_invalid_secret_when_voice_secret_is_configured(self, tmp_path):
        app = create_app(
            Settings(
                database_path=str(tmp_path / "secured-voice.db"),
                elevenlabs_webhook_secret="test-voice-secret",
                _env_file=None,
            )
        )
        client = TestClient(app)
        payload = make_elevenlabs_payload()

        rejected = client.post("/voice/elevenlabs/webhook", json=payload)
        accepted = client.post(
            "/voice/elevenlabs/webhook",
            json=payload,
            headers={"X-Voice-Webhook-Secret": "test-voice-secret"},
        )

        assert rejected.status_code == 401
        assert accepted.status_code == 200
