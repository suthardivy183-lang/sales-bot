import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_database_path() -> str:
    """On a serverless host (Vercel) only /tmp is writable, and it is
    ephemeral — good enough for a demo session, not for durable state."""
    if os.environ.get("VERCEL"):
        return "/tmp/sessions.db"
    return "sessions.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "sales-copilot"

    # WhatsApp transport (Task 0B)
    whatsapp_verify_token: str = "change-me"
    whatsapp_app_secret: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_graph_api_version: str = ""

    # ElevenLabs voice webhook tool (optional locally; required for public use)
    elevenlabs_webhook_secret: str = ""

    # Session storage (Task 1)
    database_path: str = _default_database_path()

    # LLM provider (Task 1+)
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    # A key alone must never spend credits; enable only for a controlled live test.
    llm_enabled: bool = False

    # Small-model cost routing (Task 10, optional; applies only when enabled)
    llm_routing_enabled: bool = False
    llm_model_small: str = "gemini-2.5-flash-lite"
    llm_model_large: str = "gemini-2.5-flash"

    # Google Sheets CRM (Task 5)
    google_sheets_service_account_json: str = ""
    google_sheets_spreadsheet_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
