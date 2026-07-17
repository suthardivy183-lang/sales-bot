"""Composition root: builds the orchestrator and its tools from settings."""

from app.actions.booking import BookingTool
from app.actions.crm import CrmTool, SqliteCrmBackend
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
    # Local CRM backend by default; the Google Sheets backend swaps in at
    # deployment once service-account credentials exist (same protocol).
    crm = CrmTool(SqliteCrmBackend(settings.database_path), ledger)
    return Orchestrator(
        store=SessionStore(settings.database_path),
        agent=QualificationAgent(build_extractor(settings)),
        repository=repository,
        generator=ResponseGenerator(),
        verifier=VerificationAgent(repository),
        crm=crm,
        booking=BookingTool(settings.database_path, ledger),
    )
