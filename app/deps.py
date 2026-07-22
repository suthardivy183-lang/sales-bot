"""Composition root: builds the orchestrator and its tools from settings."""

from app.actions.booking import BookingTool
from app.actions.crm import (
    CrmBackend,
    CrmTool,
    SheetsCrmBackend,
    SqliteCrmBackend,
    google_sheets_token_supplier,
)
from app.actions.ledger import ActionLedger
from app.agents.qualification import QualificationAgent
from app.agents.response import ResponseGenerator
from app.agents.verification import VerificationAgent
from app.config import Settings
from app.nlu.hybrid import build_extractor
from app.orchestrator import Orchestrator
from app.properties.repository import PropertyRepository
from app.state.store import SessionStore


def build_orchestrator(settings: Settings) -> Orchestrator:
    repository = PropertyRepository()
    ledger = ActionLedger(settings.database_path)
    crm = CrmTool(build_crm_backend(settings), ledger)
    return Orchestrator(
        store=SessionStore(settings.database_path),
        agent=QualificationAgent(build_extractor(settings)),
        repository=repository,
        generator=ResponseGenerator(),
        verifier=VerificationAgent(repository),
        crm=crm,
        booking=BookingTool(settings.database_path, ledger),
    )


def build_crm_backend(settings: Settings) -> CrmBackend:
    """Use Sheets only when the complete production configuration is present."""
    spreadsheet_id = settings.google_sheets_spreadsheet_id
    service_account_json = settings.google_sheets_service_account_json
    if bool(spreadsheet_id) != bool(service_account_json):
        raise ValueError(
            "GOOGLE_SHEETS_SPREADSHEET_ID and "
            "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON must be configured together"
        )
    if spreadsheet_id and service_account_json:
        return SheetsCrmBackend(
            spreadsheet_id=spreadsheet_id,
            token_supplier=google_sheets_token_supplier(service_account_json),
        )
    return SqliteCrmBackend(settings.database_path)
