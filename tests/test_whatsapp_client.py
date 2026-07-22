"""The Meta sender is unit-tested with a mocked HTTP transport."""

import json

import httpx
import pytest

from app.gateway.client import WhatsAppCloudSender, WhatsAppSendError


def make_sender(handler):
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return (
        WhatsAppCloudSender(
            access_token="test-access-token",
            phone_number_id="123456",
            api_version="v23.0",
            client=httpx.Client(transport=httpx.MockTransport(recording)),
        ),
        seen,
    )


def test_sends_plain_text_through_the_meta_messages_endpoint():
    sender, seen = make_sender(lambda request: httpx.Response(200, json={"messages": []}))

    sender.send_text("919999000011", "Hello from Sales Copilot")

    request = seen[0]
    assert str(request.url) == "https://graph.facebook.com/v23.0/123456/messages"
    assert request.headers["Authorization"] == "Bearer test-access-token"
    assert json.loads(request.content) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "919999000011",
        "type": "text",
        "text": {"preview_url": False, "body": "Hello from Sales Copilot"},
    }


def test_api_error_does_not_expose_the_access_token():
    sender, _ = make_sender(lambda request: httpx.Response(401, text="denied"))

    with pytest.raises(WhatsAppSendError, match="401") as exc_info:
        sender.send_text("919999000011", "Hello")

    assert "test-access-token" not in str(exc_info.value)
