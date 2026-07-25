"""Tenancy & identity models.

Multi-tenant core. An :class:`Account` is one user of the SaaS. Identity is
established by connecting an OAuth provider (Google / Discord / Slack) — there is
no separate password. Each :class:`ChannelConnection` records one connected
provider for an account and holds the (encrypted) tokens used both to identify
the user and to send replies on their behalf. Every domain row (tickets, etc.)
is scoped to an ``account_id`` so tenants are fully isolated.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Account(Base):
    """A single tenant (one user/organization using the app)."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Display identity, seeded from the first provider connected.
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    connections: Mapped[list["ChannelConnection"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Account id={self.id} email={self.email!r}>"


class ChannelConnection(Base):
    """One connected OAuth provider for an account (identity + send authorization).

    ``provider`` is google | discord | slack. ``provider_user_id`` is the stable
    id at the provider used to recognise returning users. ``external_ref`` is the
    inbound-routing key that maps a platform event back to this account+account
    (e.g. the connected mailbox address, Discord guild id, or Slack team id).
    Tokens are stored encrypted (see ``services.crypto``).
    """

    __tablename__ = "channel_connections"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_identity"),
        UniqueConstraint("provider", "external_ref", name="uq_provider_external_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    provider_user_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Inbound routing key (mailbox / guild id / team id). Nullable until known.
    external_ref: Mapped[str | None] = mapped_column(
        String(200), index=True, nullable=True
    )

    # Encrypted OAuth material.
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="connections")

    @property
    def has_refresh(self) -> bool:
        """True if a refresh token is stored (so tokens can be renewed silently)."""
        return bool(self.refresh_token_enc)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ChannelConnection id={self.id} account_id={self.account_id} "
            f"provider={self.provider!r}>"
        )
