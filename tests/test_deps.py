"""Composition-root tests for the CRM backend selection."""

import pytest

from app.actions.crm import CrmError, SheetsCrmBackend, SqliteCrmBackend, google_sheets_token_supplier
from app.config import Settings
from app.deps import build_crm_backend


def make_settings(tmp_path, **updates) -> Settings:
    return Settings(database_path=str(tmp_path / "app.db"), _env_file=None, **updates)


def test_uses_sqlite_when_sheets_is_not_configured(tmp_path):
    assert isinstance(build_crm_backend(make_settings(tmp_path)), SqliteCrmBackend)


@pytest.mark.parametrize(
    "updates",
    [
        {"google_sheets_spreadsheet_id": "sheet-123"},
        {"google_sheets_service_account_json": "{}"},
    ],
)
def test_rejects_partial_sheets_configuration(tmp_path, updates):
    with pytest.raises(ValueError, match="must be configured together"):
        build_crm_backend(make_settings(tmp_path, **updates))


def test_uses_sheets_when_both_values_are_configured(tmp_path, monkeypatch):
    monkeypatch.setattr("app.deps.google_sheets_token_supplier", lambda value: lambda: "token")
    backend = build_crm_backend(
        make_settings(
            tmp_path,
            google_sheets_spreadsheet_id="sheet-123",
            google_sheets_service_account_json="{}",
        )
    )

    assert isinstance(backend, SheetsCrmBackend)


def test_rejects_malformed_service_account_json():
    with pytest.raises(CrmError, match="Invalid Google Sheets"):
        google_sheets_token_supplier("not-json")
