import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

TEST_VERIFY_TOKEN = "test-verify-token"


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        whatsapp_verify_token=TEST_VERIFY_TOKEN, _env_file=None
    )
    return TestClient(app)


def make_whatsapp_payload(
    text: str = "I want a flat in Ahmedabad",
    wa_id: str = "919999000011",
    message_id: str = "wamid.TEST-0001",
) -> dict:
    """Mocked WhatsApp Cloud API webhook payload with a single text message."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "TEST-WABA-ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001111",
                                "phone_number_id": "TEST-PHONE-ID",
                            },
                            "contacts": [
                                {"profile": {"name": "Test Lead"}, "wa_id": wa_id}
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": "1770000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def make_status_payload() -> dict:
    """Delivery-receipt payload (no messages key) — must be acknowledged, not answered."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "TEST-WABA-ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": "wamid.TEST-0001", "status": "delivered"}
                            ],
                        },
                    }
                ],
            }
        ],
    }
