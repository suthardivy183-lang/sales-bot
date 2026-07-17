"""Task 0A: a mocked WhatsApp payload posted locally must get a reply back."""

from app.gateway.router import HARDCODED_REPLY
from app.privacy import mask_phone
from tests.conftest import TEST_VERIFY_TOKEN, make_status_payload, make_whatsapp_payload


class TestReceiveWebhook:
    def test_mock_message_round_trips_with_reply(self, client):
        response = client.post("/webhook", json=make_whatsapp_payload())

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "received"
        assert len(body["replies"]) == 1
        assert body["replies"][0]["reply"] == HARDCODED_REPLY

    def test_reply_never_exposes_full_phone_number(self, client):
        wa_id = "919999000011"
        response = client.post("/webhook", json=make_whatsapp_payload(wa_id=wa_id))

        assert wa_id not in response.text
        assert response.json()["replies"][0]["to"] == mask_phone(wa_id)

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


class TestMaskPhone:
    def test_masks_all_but_last_four_digits(self):
        assert mask_phone("919999000011") == "********0011"

    def test_short_values_are_fully_masked(self):
        assert mask_phone("911") == "***"
