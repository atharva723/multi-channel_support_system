"""Application entrypoint.

Builds the FastAPI application, manages startup/shutdown via an async lifespan
(creating the SQLite schema on boot and disposing the engine on shutdown), and
exposes a ``/health`` probe. Feature routers (triage, tickets, SSE stream) are
mounted here in later phases.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_db, init_db
from app.services.embeddings import close_embedding_client
from app.services.llm_router import close_llm_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the database schema on startup; dispose resources on shutdown."""
    await init_db()
    yield
    await close_llm_router()
    await close_embedding_client()
    await dispose_db()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
