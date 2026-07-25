"""Gmail poller (inbound ingestion for email).

Run as a **separate process** from the FastAPI server:

    python -m app.workers.gmail_poller

The Gmail equivalent of the Discord gateway bot. Every ``poll_interval`` seconds
it iterates over all connected Google accounts and, using each account's stored
(encrypted) OAuth token, fetches new inbox messages via the Gmail API. Each new
email is normalized and POSTed to ``/support/triage`` with the mailbox address as
``external_ref`` so the backend attributes it to the right tenant. Triage,
escalation (SSE) and reply-sending are handled by the FastAPI process exactly as
for Discord.

Why HTTP-forward instead of triaging in-process: the SSE event broker is an
in-memory singleton in the FastAPI process; escalations must be published there.

Design notes:
  * Needs a **refresh token** on the connection to keep reading past ~1h; it
    refreshes the access token when expired and persists the new one.
  * De-dupes using Gmail's internal timestamp per connection (last_seen_ts),
    stored in a tiny ``poller_state`` table, plus the DB unique constraint on
    (account, channel, message_id) as a backstop.
  * No public URL required (pure outbound Gmail API calls).
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.account import ChannelConnection
from app.services import connections as conn_store
from app.services.providers import ProviderError, get_provider

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sentinel.gmail")

_TRIAGE_URL = f"{settings.app_base_url}{settings.api_v1_prefix}/support/triage"


async def _ensure_state_table() -> None:
    """Create the poller_state table if missing (idempotent)."""
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS poller_state ("
            "connection_id INTEGER PRIMARY KEY, last_seen_ts INTEGER NOT NULL)"
        )


async def _get_last_seen(db: AsyncSession, connection_id: int) -> int:
    row = (
        await db.execute(
            text("SELECT last_seen_ts FROM poller_state WHERE connection_id = :cid"),
            {"cid": connection_id},
        )
    ).first()
    return int(row[0]) if row else 0


async def _set_last_seen(db: AsyncSession, connection_id: int, ts: int) -> None:
    await db.execute(
        text(
            "INSERT INTO poller_state (connection_id, last_seen_ts) "
            "VALUES (:cid, :ts) "
            "ON CONFLICT(connection_id) DO UPDATE SET last_seen_ts = :ts"
        ),
        {"cid": connection_id, "ts": ts},
    )
    await db.commit()


async def _refresh_if_needed(db: AsyncSession, conn: ChannelConnection):
    """Return usable tokens, refreshing + persisting if the access token expired."""
    tokens = conn_store.load_tokens(conn)
    if conn_store.is_expired(conn) and tokens.refresh_token:
        provider = get_provider("google")
        try:
            new_tokens = await provider.refresh(tokens.refresh_token)
            from app.services.providers import ProviderIdentity

            conn_store._apply_tokens(  # noqa: SLF001 - internal reuse
                conn,
                new_tokens,
                ProviderIdentity(
                    provider_user_id=conn.provider_user_id,
                    email=conn.email,
                    display_name=conn.display_name,
                    external_ref=conn.external_ref,
                ),
            )
            await db.commit()
            return new_tokens
        except (ProviderError, NotImplementedError) as exc:
            log.warning("Token refresh failed for %s: %s", conn.email, exc)
    return tokens


async def _forward_email(email: dict, mailbox: str) -> None:
    payload = {
        "channel": "email",
        "channel_id": email.get("thread_id") or mailbox,
        "message_id": str(email["message_id"]),
        "author_name": email.get("from_name") or email.get("from_email") or "Unknown",
        "author_contact": email.get("from_email") or "",
        "content": f"{email.get('subject', '')}\n\n{email.get('body', '')}".strip(),
        "external_ref": mailbox,
    }
    headers = {}
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(_TRIAGE_URL, json=payload, headers=headers)
    if resp.status_code >= 300:
        log.warning("Triage rejected email %s: %s %s", email["message_id"], resp.status_code, resp.text)
    else:
        data = resp.json()
        log.info(
            "Triaged email %s from %s -> %s (crit=%.3f)",
            email["message_id"],
            payload["author_contact"],
            data.get("decision"),
            data.get("criticality_score", 0.0),
        )


async def _poll_once() -> None:
    provider = get_provider("google")
    async with AsyncSessionLocal() as db:
        conns = list(
            (
                await db.scalars(
                    select(ChannelConnection).where(ChannelConnection.provider == "google")
                )
            ).all()
        )
        for conn in conns:
            mailbox = conn.external_ref or conn.email
            if not mailbox:
                continue
            try:
                tokens = await _refresh_if_needed(db, conn)
                last_seen = await _get_last_seen(db, conn.id)
                # On first run, only look at the last 5 minutes to avoid a flood.
                after = last_seen or (int(time.time()) - 300)
                emails = await provider.list_new_messages(tokens, after_epoch=after)
                # Oldest first so ordering is natural.
                emails.sort(key=lambda e: e.get("internal_ts", 0))
                newest = last_seen
                for email in emails:
                    ts = email.get("internal_ts", 0)
                    if ts <= last_seen:
                        continue
                    await _forward_email(email, mailbox)
                    newest = max(newest, ts)
                if newest > last_seen:
                    await _set_last_seen(db, conn.id, newest)
            except ProviderError as exc:
                log.warning("Gmail poll failed for %s: %s", mailbox, exc)
            except Exception as exc:  # noqa: BLE001 - keep the poller alive
                log.exception("Unexpected error polling %s: %s", mailbox, exc)


async def main() -> None:
    await _ensure_state_table()
    interval = settings.gmail_poll_interval
    log.info("Gmail poller started (every %ss). Triage -> %s", interval, _TRIAGE_URL)
    while True:
        await _poll_once()
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
