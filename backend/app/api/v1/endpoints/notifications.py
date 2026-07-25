"""Push notification registration endpoints.

The mobile app obtains an Expo push token on the device and registers it here so
the backend can deliver escalation alerts. All routes are tenant-scoped.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAccount, DBSession
from app.models.account import Account
from app.services import push as push_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushTokenIn(BaseModel):
    """Body for registering / unregistering a device push token."""

    token: str
    platform: str | None = None


@router.post(
    "/register",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Register this device's Expo push token",
)
async def register_push_token(
    payload: PushTokenIn,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> None:
    await push_service.register_token(
        db, account_id=account.id, token=payload.token, platform=payload.platform
    )


@router.post(
    "/unregister",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove this device's push token (e.g. on sign-out)",
)
async def unregister_push_token(
    payload: PushTokenIn,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> None:
    await push_service.unregister_token(
        db, account_id=account.id, token=payload.token
    )
