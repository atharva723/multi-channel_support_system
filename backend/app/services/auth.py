"""App session tokens (JWT).

After a user connects an OAuth provider, we issue our own short-lived app session
JWT carrying the ``account_id``. The mobile client sends it as a Bearer token on
every request; the ``require_account`` dependency decodes it and scopes all data
access to that tenant. This is separate from the *provider* OAuth tokens (which
live encrypted in the DB and are used only for sending) — this token is purely
your app's session.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


class SessionTokenError(RuntimeError):
    """Raised when a session token is missing, invalid, or expired."""


def create_session_token(account_id: int) -> str:
    """Mint a signed JWT session token for an account."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
        "typ": "session",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> int:
    """Validate a session token and return its ``account_id``."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise SessionTokenError("Session token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise SessionTokenError("Invalid session token.") from exc

    sub = payload.get("sub")
    if sub is None:
        raise SessionTokenError("Session token missing subject.")
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise SessionTokenError("Malformed account id in token.") from exc


def create_oauth_state(
    provider: str,
    link_account_id: int | None = None,
    redirect_to: str | None = None,
) -> str:
    """Create a short-lived signed state token for an OAuth round-trip.

    Encodes the provider, the optional account to link the new connection to,
    and an optional client-supplied ``redirect_to`` (the mobile app's deep link)
    so the callback can return the session token to the right place. Protects
    against CSRF without server-side session storage.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "provider": provider,
        "link": link_account_id,
        "redirect_to": redirect_to,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "typ": "oauth_state",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_oauth_state(state: str) -> tuple[str, int | None, str | None]:
    """Validate an OAuth state token; return ``(provider, link, redirect_to)``."""
    try:
        payload = jwt.decode(
            state, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise SessionTokenError("Invalid or expired OAuth state.") from exc
    if payload.get("typ") != "oauth_state":
        raise SessionTokenError("Wrong token type for OAuth state.")
    return payload.get("provider"), payload.get("link"), payload.get("redirect_to")
