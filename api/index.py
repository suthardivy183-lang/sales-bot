"""Vercel serverless entrypoint — exposes the FastAPI ASGI app.

Vercel's Python runtime imports `app` from this module and serves it. All
routes (chat simulator at /, webhook, health) are defined on the app itself.
"""

from app.main import app

__all__ = ["app"]
