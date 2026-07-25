"""Expo push notification delivery.

Sends notifications to an account's registered devices via the Expo Push API
(https://exp.host/--/api/v2/push/send). Best-effort: failures never break the
triage pipeline. Tokens Expo reports as ``DeviceNotRegistered`` are pruned so we
stop pushing to uninstalled/stale devices.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push import PushToken

logger = logging.getLogger("sentinel.push")

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_ANDROID_CHANNEL = "escalations"


async def register_token(
    db: AsyncSession, *, account_id: int, token: str, platform: str | None
) -> PushToken:
    """Upsert a device push token for an account.

    If the token already exists it is re-pointed at this account (handles a
    device that switched accounts); otherwise a new row is created.
    """
    existing = (
        await db.scalars(select(PushToken).where(PushToken.token == token))
    ).first()
    if existing is not None:
        existing.account_id = account_id
        existing.platform = platform
        await db.commit()
        await db.refresh(existing)
        return existing

    row = PushToken(account_id=account_id, token=token, platform=platform)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def unregister_token(db: AsyncSession, *, account_id: int, token: str) -> None:
    """Remove a device token (e.g. on sign-out)."""
    await db.execute(
        delete(PushToken).where(
            PushToken.token == token, PushToken.account_id == account_id
        )
    )
    await db.commit()


async def send_to_account(
    db: AsyncSession,
    *,
    account_id: int,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Send a push notification to every device registered for an account.

    Best-effort: any transport error is logged and swallowed. Tokens reported as
    ``DeviceNotRegistered`` by Expo are deleted.
    """
    tokens = list(
        (
            await db.scalars(
                select(PushToken.token).where(PushToken.account_id == account_id)
            )
        ).all()
    )
    if not tokens:
        return

    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {},
            "sound": "default",
            "channelId": _ANDROID_CHANNEL,
            "priority": "high",
        }
        for token in tokens
    ]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _EXPO_PUSH_URL,
                json=messages,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        if resp.status_code >= 300:
            logger.warning("Expo push failed: %s %s", resp.status_code, resp.text)
            return
        await _prune_dead_tokens(db, tokens, resp.json())
    except httpx.HTTPError as exc:
        logger.warning("Expo push transport error: %s", exc)


async def _prune_dead_tokens(
    db: AsyncSession, tokens: list[str], response: dict[str, Any]
) -> None:
    """Delete tokens Expo flagged as DeviceNotRegistered (aligned by index)."""
    receipts = response.get("data")
    if not isinstance(receipts, list):
        return
    dead: list[str] = []
    for token, receipt in zip(tokens, receipts):
        if (
            isinstance(receipt, dict)
            and receipt.get("status") == "error"
            and (receipt.get("details") or {}).get("error") == "DeviceNotRegistered"
        ):
            dead.append(token)
    if dead:
        await db.execute(delete(PushToken).where(PushToken.token.in_(dead)))
        await db.commit()
        logger.info("Pruned %d dead push token(s)", len(dead))
