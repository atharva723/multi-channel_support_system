"""SQLAlchemy ORM models for the Sentinel backend.

Uses the SQLAlchemy 2.x typed ``Mapped`` style on the shared async ``Base``.
Mirrors the ``support_tickets`` schema from the specification.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Ticket(Base):
    """A single ingested support request and its triage results."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        # message_id is unique WITHIN an account+channel, not globally: different
        # tenants (and channels) may legitimately reuse the same platform id.
        UniqueConstraint(
            "account_id", "channel", "message_id", name="uq_account_channel_message"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Tenancy -----------------------------------------------------------
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # --- Source metadata ---------------------------------------------------
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    message_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    author_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Sentiment & urgency metrics --------------------------------------
    criticality_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # --- LLM outputs & workflow state -------------------------------------
    ai_draft_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PENDING, APPROVED, MODIFIED, DISMISSED
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Ticket id={self.id} channel={self.channel!r} "
            f"status={self.status!r} urgency={self.urgency_score:.2f}>"
        )
