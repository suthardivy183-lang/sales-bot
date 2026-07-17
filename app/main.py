from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.deps import build_orchestrator
from app.gateway.router import router as gateway_router

_SIMULATOR_PAGE = Path(__file__).parent / "static" / "simulator.html"


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title="Sales Copilot", docs_url=None, redoc_url=None)
    app.state.orchestrator = build_orchestrator(app_settings)
    app.include_router(gateway_router)

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
