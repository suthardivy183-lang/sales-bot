from fastapi import FastAPI

from app.gateway.router import router as gateway_router


def create_app() -> FastAPI:
    app = FastAPI(title="Sales Copilot", docs_url=None, redoc_url=None)
    app.include_router(gateway_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
