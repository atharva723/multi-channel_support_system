"""Async database layer.

Sets up the SQLAlchemy 2.x async engine (``sqlite+aiosqlite``), a session
factory, the declarative ``Base`` all models inherit from, and helpers to
initialise/dispose the schema. ``init_db`` is wired into the FastAPI lifespan so
tables exist on startup.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Called from the application lifespan on startup.

    Imports the models module for its side effect of registering tables on
    ``Base.metadata`` before ``create_all`` runs.
    """
    from app import models  # noqa: F401  (ensures models are imported)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Dispose the engine's connection pool on shutdown."""
    await engine.dispose()
