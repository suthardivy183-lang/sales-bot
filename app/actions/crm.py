"""CRM lead writes — a tool, not an agent (engineering rule 5).

Two backends behind one protocol: SQLite (works everywhere, used in tests and
as the local ledger of record) and Google Sheets (the live demo sheet, REST
via httpx). Idempotency lives in CrmTool via the ActionLedger, so replays are
safe with either backend.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Protocol

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from app.actions.ledger import ActionLedger
from app.actions.models import CrmError, CrmLead, CrmWriteResult
from app.privacy import mask_phone
from app.state.models import SessionState

CRM_ACTION = "crm_lead"
GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"

SHEET_COLUMNS = (
    "created_at",
    "session_id",
    "wa_id_masked",
    "intent",
    "locality",
    "budget_min",
    "budget_max",
    "bhk",
    "timeline",
    "stage",
    "property_id",
    "note",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS crm_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    session_id TEXT NOT NULL,
    wa_id_masked TEXT NOT NULL,
    intent TEXT,
    locality TEXT,
    budget_min INTEGER,
    budget_max INTEGER,
    bhk INTEGER,
    timeline TEXT,
    stage TEXT NOT NULL,
    property_id INTEGER,
    note TEXT NOT NULL
)
"""


class CrmBackend(Protocol):
    def append_lead(self, lead: CrmLead) -> None: ...


class SqliteCrmBackend:
    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def append_lead(self, lead: CrmLead) -> None:
        columns = ", ".join(SHEET_COLUMNS)
        placeholders = ", ".join("?" for _ in SHEET_COLUMNS)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO crm_leads ({columns}) VALUES ({placeholders})",
                tuple(getattr(lead, column) for column in SHEET_COLUMNS),
            )

    def all_leads(self) -> list[CrmLead]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM crm_leads ORDER BY id"
            ).fetchall()
        return [
            CrmLead(**{column: row[column] for column in SHEET_COLUMNS})
            for row in rows
        ]


class SheetsCrmBackend:
    """Appends one row per lead to a Google Sheet via the values.append API.

    token_supplier returns a short-lived OAuth access token (service account);
    injecting it keeps this class testable without Google credentials.
    """

    def __init__(
        self,
        spreadsheet_id: str,
        token_supplier: Callable[[], str],
        sheet_range: str = "Leads!A:L",
        client: httpx.Client | None = None,
    ):
        self._spreadsheet_id = spreadsheet_id
        self._token_supplier = token_supplier
        self._sheet_range = sheet_range
        self._client = client or httpx.Client(timeout=15)

    def append_lead(self, lead: CrmLead) -> None:
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self._spreadsheet_id}/values/{self._sheet_range}:append"
        )
        row = [
            "" if getattr(lead, column) is None else str(getattr(lead, column))
            for column in SHEET_COLUMNS
        ]
        try:
            response = self._client.post(
                url,
                params={"valueInputOption": "RAW"},
                json={"values": [row]},
                headers={"Authorization": f"Bearer {self._token_supplier()}"},
            )
        except httpx.HTTPError as exc:
            raise CrmError(f"Sheets request failed: {exc!r}") from exc
        if response.status_code != 200:
            raise CrmError(
                f"Sheets API returned {response.status_code}: {response.text[:200]}"
            )


def google_sheets_token_supplier(service_account_json: str) -> Callable[[], str]:
    """Build a refreshable access-token supplier from an environment value.

    The complete service-account JSON stays in the host's secret store; no key
    file needs to be present in the deployed container or repository.
    """
    try:
        info = json.loads(service_account_json)
        if not isinstance(info, dict):
            raise ValueError("service-account JSON must be an object")
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[GOOGLE_SHEETS_SCOPE]
        )
    except (ValueError, TypeError) as exc:
        raise CrmError("Invalid Google Sheets service-account configuration") from exc

    request = GoogleAuthRequest()

    def get_token() -> str:
        if not credentials.valid:
            credentials.refresh(request)
        if not credentials.token:
            raise CrmError("Google Sheets service account did not return an access token")
        return credentials.token

    return get_token


class CrmTool:
    def __init__(self, backend: CrmBackend, ledger: ActionLedger):
        self._backend = backend
        self._ledger = ledger

    def write_lead(
        self,
        message_id: str,
        state: SessionState,
        note: str = "",
        property_id: int | None = None,
    ) -> CrmWriteResult:
        replayed = self._ledger.get(message_id, CRM_ACTION)
        if replayed is not None:
            return CrmWriteResult(created=False, lead=CrmLead(**replayed))

        lead = lead_from_state(state, note=note, property_id=property_id)
        self._backend.append_lead(lead)
        self._ledger.record(message_id, CRM_ACTION, lead.model_dump())
        return CrmWriteResult(created=True, lead=lead)


def lead_from_state(
    state: SessionState, note: str = "", property_id: int | None = None
) -> CrmLead:
    return CrmLead(
        session_id=state.session_id,
        wa_id_masked=mask_phone(state.wa_id),
        intent=state.intent,
        locality=state.locality,
        budget_min=state.budget_min,
        budget_max=state.budget_max,
        bhk=state.bhk,
        timeline=state.timeline,
        stage=state.stage,
        property_id=property_id
        if property_id is not None
        else state.selected_property_id,
        note=note,
        created_at=datetime.now(UTC).isoformat(),
    )
