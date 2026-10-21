"""FastAPI entry point.

Run from backend/:  uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import banking, crypto, experiments, health, qkd
from app.config import get_settings
from app.db.database import Database


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db.create_all()
        yield
        app.state.db.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="BB84 QKD + AES-256-GCM educational banking simulation.",
        lifespan=lifespan,
    )
    app.state.db = Database(settings.database_url)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, qkd, crypto, banking, experiments):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
