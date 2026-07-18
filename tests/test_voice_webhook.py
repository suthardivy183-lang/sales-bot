"""V1: ElevenLabs voice turns reuse the existing sales orchestrator."""


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
