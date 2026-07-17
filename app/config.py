from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "sales-copilot"

    # WhatsApp transport (Task 0B)
    whatsapp_verify_token: str = "change-me"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""

    # Session storage (Task 1)
    database_path: str = "sessions.db"

    # LLM provider (Task 1+)
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"

    # Small-model cost routing (Task 10, optional; off by default)
    llm_routing_enabled: bool = False
    llm_model_small: str = "gemini-2.5-flash-lite"
    llm_model_large: str = "gemini-2.5-flash"

    # Google Sheets CRM (Task 5)
    google_sheets_credentials_file: str = ""
    google_sheets_spreadsheet_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
