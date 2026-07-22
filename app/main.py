from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.actions.ledger import ActionLedger
from app.gateway.client import WhatsAppCloudSender
from app.deps import build_orchestrator
from app.gateway.router import router as gateway_router
from app.voice.router import router as voice_router

_SIMULATOR_PAGE = Path(__file__).parent / "static" / "simulator.html"


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title="Sales Copilot", docs_url=None, redoc_url=None)
    app.state.orchestrator = build_orchestrator(app_settings)
    app.state.whatsapp_reply_ledger = ActionLedger(app_settings.database_path)
    app.state.whatsapp_sender = (
        WhatsAppCloudSender(
            access_token=app_settings.whatsapp_access_token,
            phone_number_id=app_settings.whatsapp_phone_number_id,
            api_version=app_settings.whatsapp_graph_api_version,
        )
        if app_settings.whatsapp_access_token
        and app_settings.whatsapp_phone_number_id
        and app_settings.whatsapp_graph_api_version
        else None
    )
    app.include_router(gateway_router)
    app.include_router(voice_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/")
    def simulator() -> FileResponse:
        """Browser chat simulator — a dev/demo front door onto /webhook.

        Not the production channel; WhatsApp (Task 0B) is the real transport.
        """
        return FileResponse(_SIMULATOR_PAGE, media_type="text/html")

    return app


app = create_app()
