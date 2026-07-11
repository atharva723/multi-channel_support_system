"""Shared FastAPI dependencies.

Centralizes the wiring used by route handlers: the async DB session, the LLM
router singleton, and an optional API-key guard for endpoints exposed to n8n.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.account import Account
from app.services.auth import SessionTokenError, decode_session_token
from app.services.events import EventBroker, get_event_broker
from app.services.llm_router import LLMRouter, get_llm_router


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session (re-exported from the database layer)."""
    async for session in get_session():
        yield session


def get_router() -> LLMRouter:
    """Provide the process-wide LLM router singleton."""
    return get_llm_router()


def get_broker() -> EventBroker:
    """Provide the process-wide real-time event broker singleton."""
    return get_event_broker()


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Guard protected endpoints with a shared secret when one is configured.

    If ``settings.api_key`` is empty (local dev), the check is a no-op. When set,
    callers (e.g. the n8n HTTP Request node) must send a matching ``X-API-Key``.
    """
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


async def require_account(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Account:
    """Resolve the current tenant from the Bearer session token.

    Every tenant-scoped endpoint depends on this: it decodes the app JWT, loads
    the owning ``Account``, and hands it to the handler so all queries can be
    filtered by ``account.id``. Rejects missing/invalid/expired tokens with 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        account_id = decode_session_token(token)
    except SessionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer exists.",
        )
    return account


# Convenience aliases for readable route signatures.
DBSession = Depends(get_db)
Router = Depends(get_router)
Broker = Depends(get_broker)
ApiKeyGuard = Depends(require_api_key)
CurrentAccount = Depends(require_account)
