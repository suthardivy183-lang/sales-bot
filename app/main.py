from fastapi import FastAPI

from app.config import Settings, get_settings
from app.deps import build_orchestrator
from app.gateway.router import router as gateway_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title="Sales Copilot", docs_url=None, redoc_url=None)
    app.state.orchestrator = build_orchestrator(app_settings)
    app.include_router(gateway_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
