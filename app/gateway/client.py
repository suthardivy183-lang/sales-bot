"""Outbound WhatsApp Cloud API transport.

The webhook and orchestration code remain provider-neutral; this client owns
the one Meta-specific HTTP request used for real text replies.
"""

import httpx


class WhatsAppSendError(RuntimeError):
    """The Cloud API rejected, or could not receive, an outbound message."""


class WhatsAppCloudSender:
    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        api_version: str,
        client: httpx.Client | None = None,
    ):
        self._access_token = access_token
        self._url = (
            f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        )
        self._client = client or httpx.Client(timeout=15)

    def send_text(self, recipient: str, body: str) -> None:
        try:
            response = self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": recipient,
                    "type": "text",
                    "text": {"preview_url": False, "body": body},
                },
            )
        except httpx.HTTPError as exc:
            raise WhatsAppSendError(f"Cloud API request failed: {exc!r}") from exc
        if response.status_code // 100 != 2:
            raise WhatsAppSendError(
                f"Cloud API returned {response.status_code}: {response.text[:200]}"
            )
