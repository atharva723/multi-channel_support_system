"""Schemas for accounts, sessions, and channel connections."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AccountOut(BaseModel):
    """Public view of a tenant account."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    email: Optional[str] = None
    created_at: datetime


class ConnectionOut(BaseModel):
    """A connected provider (no secrets exposed)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    external_ref: Optional[str] = None
    scopes: Optional[str] = None
    created_at: datetime


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
