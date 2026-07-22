"""Task 0A/0B: mocked WhatsApp webhook behavior and transport security."""

import hashlib
import hmac
import json

from app.gateway.client import WhatsAppSendError
from app.privacy import mask_phone
from tests.conftest import (
    TEST_APP_SECRET,
    TEST_VERIFY_TOKEN,
    make_status_payload,
    make_test_settings,
    make_whatsapp_payload,
)


class RecordingSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, recipient: str, body: str) -> None:
        self.sent.append((recipient, body))


class FailingSender:
    def send_text(self, recipient: str, body: str) -> None:
        raise WhatsAppSendError("simulated transport failure")


def signed_payload(payload: dict) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(TEST_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={signature}",
    }


class TestReceiveWebhook:
    def test_mock_message_round_trips_with_reply(self, client):
        response = client.post("/webhook", json=make_whatsapp_payload())

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "received"
        assert len(body["replies"]) == 1
        # "I want a flat in Ahmedabad" sets the buy intent, so the
        # orchestrated reply asks the next qualification question: budget.
        assert "budget" in body["replies"][0]["reply"].lower()

    def test_reply_never_exposes_full_phone_number(self, client):
        wa_id = "919999000011"
        response = client.post("/webhook", json=make_whatsapp_payload(wa_id=wa_id))

        assert wa_id not in response.text
        assert response.json()["replies"][0]["to"] == mask_phone(wa_id)

    def test_configured_sender_delivers_the_verified_reply(self, client):
        sender = RecordingSender()
        client.app.state.whatsapp_sender = sender

        response = client.post("/webhook", json=make_whatsapp_payload())

        assert response.status_code == 200
        assert sender.sent == [("919999000011", response.json()["replies"][0]["reply"])]
        assert response.json()["replies"][0]["delivered"] is True

    def test_replayed_message_is_not_sent_twice(self, client):
        sender = RecordingSender()
        client.app.state.whatsapp_sender = sender
        payload = make_whatsapp_payload(message_id="wamid.REPLAY-1")

        first = client.post("/webhook", json=payload)
        replay = client.post("/webhook", json=payload)

        assert first.status_code == replay.status_code == 200
        assert first.json()["replies"] == replay.json()["replies"]
        assert len(sender.sent) == 1

    def test_sender_failure_is_acknowledged_and_can_be_retried(self, client):
        client.app.state.whatsapp_sender = FailingSender()
        payload = make_whatsapp_payload(message_id="wamid.SEND-FAILURE")

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        assert response.json()["replies"][0]["delivered"] is False

    def test_status_only_payload_is_acknowledged_without_reply(self, client):
        response = client.post("/webhook", json=make_status_payload())

        assert response.status_code == 200
        assert response.json() == {"status": "ignored", "replies": []}

    def test_malformed_payload_is_rejected(self, client):
        response = client.post("/webhook", json={"not": "a whatsapp payload"})

        assert response.status_code == 422


class TestVerifyWebhook:
    def test_correct_token_echoes_challenge(self, client):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": TEST_VERIFY_TOKEN,
                "hub.challenge": "challenge-12345",
            },
        )

        assert response.status_code == 200
        assert response.text == "challenge-12345"

    def test_wrong_token_is_rejected(self, client):
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge-12345",
            },
        )

        assert response.status_code == 403


class TestWebhookSignature:
    def test_valid_signature_is_accepted(self, tmp_path):
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.main import create_app

        settings = make_test_settings(tmp_path).model_copy(
            update={"whatsapp_app_secret": TEST_APP_SECRET}
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        body, headers = signed_payload(make_whatsapp_payload())

        with TestClient(app) as signed_client:
            response = signed_client.post("/webhook", content=body, headers=headers)

        assert response.status_code == 200

    def test_missing_or_invalid_signature_is_rejected(self, tmp_path):
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.main import create_app

        settings = make_test_settings(tmp_path).model_copy(
            update={"whatsapp_app_secret": TEST_APP_SECRET}
        )
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        body, headers = signed_payload(make_whatsapp_payload())
        headers["X-Hub-Signature-256"] = "sha256=not-a-real-signature"

        with TestClient(app) as signed_client:
            response = signed_client.post("/webhook", content=body, headers=headers)

        assert response.status_code == 403


class TestMaskPhone:
    def test_masks_all_but_last_four_digits(self):
        assert mask_phone("919999000011") == "********0011"

    def test_short_values_are_fully_masked(self):
        assert mask_phone("911") == "***"
