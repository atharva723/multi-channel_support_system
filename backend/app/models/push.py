"""Push notification device tokens.

Each row is one Expo push token belonging to an account's device. A single
account can have several (multiple devices / reinstalls), so escalations fan out
to all of an account's registered tokens. Tokens are pruned when Expo reports
them as ``DeviceNotRegistered``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PushToken(Base):
    """An Expo push token registered by an account's device."""

    __tablename__ = "push_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # The Expo push token string, e.g. "ExponentPushToken[xxxxxxxx]". Unique so a
    # device that re-registers updates its owner rather than duplicating.
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PushToken id={self.id} account_id={self.account_id}>"
