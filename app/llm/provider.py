"""Provider-agnostic LLM interface.

Only one implementation (Gemini) needs to work for the hackathon; the protocol
exists so swapping providers touches nothing outside app/llm/.
"""

from typing import Protocol


class LLMProviderError(RuntimeError):
    """Raised when the provider fails; callers degrade to rules-only extraction."""


class LLMProvider(Protocol):
    def generate_json(self, *, system: str, user: str) -> dict:
        """Return the model's response parsed as a JSON object."""
        ...
