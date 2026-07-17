"""The browser chat simulator is a dev/demo front door onto the same /webhook.

These tests prove it is served and that its documented contract — post a
WhatsApp-shaped payload, read replies[0].reply — is exactly what the page uses.
"""


class TestSimulatorPage:
    def test_root_serves_the_simulator_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    def test_page_posts_to_the_real_webhook(self, client):
        body = client.get("/").text
        assert 'fetch("/webhook"' in body
        # It reads the same envelope the webhook returns.
        assert "data.replies" in body

    def test_page_labels_itself_as_a_simulator_not_production(self, client):
        body = client.get("/").text.lower()
        assert "simulator" in body
        assert "not the production channel" in body


class TestSimulatorDrivesTheRealFlow:
    """The page's payload shape must drive the orchestrator end to end."""

    def _payload(self, text, message_id, wa_id="915550001100"):
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "SIM",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "messages": [{
                            "from": wa_id,
                            "id": message_id,
                            "timestamp": "1770000000",
                            "type": "text",
                            "text": {"body": text},
                        }],
                    },
                }],
            }],
        }

    def test_simulated_turn_returns_a_verified_reply(self, client):
        reply = client.post(
            "/webhook",
            json=self._payload("2BHK in Bopal under 70 lakh, buying", "wamid.SIM-1"),
        ).json()["replies"][0]["reply"]
        assert "2BHK in Bopal" in reply
        assert "property #1" in reply

    def test_trap_question_is_refused_through_the_simulator_shape(self, client):
        client.post(
            "/webhook",
            json=self._payload("buying 3BHK in Bopal under 90 lakh", "wamid.SIM-a"),
        )
        reply = client.post(
            "/webhook",
            json=self._payload(
                "Does the Shela property have a private pool?", "wamid.SIM-b"
            ),
        ).json()["replies"][0]["reply"]
        assert "can't confirm" in reply
        assert "yes" not in reply.lower()
