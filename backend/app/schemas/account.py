"""Schemas for accounts, sessions, and channel connections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field


class AccountOut(BaseModel):
    """Public view of a tenant account."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    email: Optional[str] = None
    created_at: datetime


class ConnectionOut(BaseModel):
    """A connected provider (no secrets exposed).

    ``needs_reconnect`` is a derived health flag the mobile Channels screen uses
    to prompt the user to re-authenticate: it is true when the access token has
    expired and there is no refresh token to silently renew it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    external_ref: Optional[str] = None
    scopes: Optional[str] = None
    created_at: datetime
    token_expires_at: Optional[datetime] = None

    # Populated from the ORM's ``refresh_token_enc`` via a pre-validator alias.
    has_refresh: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_reconnect(self) -> bool:
        if self.has_refresh:
            return False
        if self.token_expires_at is None:
            return False
        exp = self.token_expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp <= datetime.now(timezone.utc)



class SessionOut(BaseModel):
    """Issued after a successful OAuth connect."""

    access_token: str
    token_type: str = "bearer"
    account: AccountOut
    connected_provider: str
    is_new_account: bool


class MeOut(BaseModel):
    """Current account plus its connections."""

    account: AccountOut
    connections: list[ConnectionOut]


class ExchangeRequest(BaseModel):
    """Body for POST /auth/{provider}/exchange (Option B, app-owned OAuth).

    Discord (PKCE): send ``code`` + ``code_verifier`` + ``redirect_uri``.
    Google (native SDK): send ``server_auth_code``.
    Optional ``link_account_id`` attaches this connection to an existing account
    (adding a channel while already signed in).
    """

    code: Optional[str] = None
    code_verifier: Optional[str] = None
    redirect_uri: Optional[str] = None
    server_auth_code: Optional[str] = None
    link_account_id: Optional[int] = None

