"""Gemini implementation of the LLM provider (REST, JSON-mode responses).

The API key travels in the x-goog-api-key header — never in the URL — so it
cannot leak through request logs (engineering rule 8).
"""

import json

import httpx

from app.llm.provider import LLMProviderError

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT_SECONDS = 30


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        client: httpx.Client | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS)

    def generate_json(self, *, system: str, user: str) -> dict:
        url = f"{GEMINI_BASE_URL}/models/{self._model}:generateContent"
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0,
            },
        }
        try:
            response = self._client.post(
                url, json=body, headers={"x-goog-api-key": self._api_key}
            )
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Gemini request failed: {exc!r}") from exc

        if response.status_code != 200:
            raise LLMProviderError(
                f"Gemini API returned {response.status_code}: {response.text[:200]}"
            )
        try:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError("Gemini response did not contain JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMProviderError("Gemini response JSON was not an object")
        return parsed
