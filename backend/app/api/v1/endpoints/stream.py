"""Server-Sent Events (SSE) gateway.

``GET /support/stream`` is the real-time pipeline described in the spec's
"Real-Time Handshake" step. The Expo dashboard opens this single long-lived
connection; the server then pushes a compact event the moment a critical ticket
is escalated (``escalation``) or an agent action changes a ticket
(``ticket_update``). This avoids battery-draining polling and lets the mobile
client fire a haptic pulse and prepend the card instantly.

Implementation uses ``sse-starlette``'s ``EventSourceResponse`` driven by an
async generator that pulls from this connection's broker queue. A periodic
keepalive comment keeps intermediaries from closing an idle connection, and the
generator exits cleanly when the client disconnects.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from app.api.deps import Broker
from app.models.account import Account
from app.services.auth import SessionTokenError, decode_session_token
from app.services.events import EventBroker

router = APIRouter(prefix="/support", tags=["stream"])

# Seconds between keepalive pings when no events are flowing.
_KEEPALIVE_INTERVAL = 15.0


@router.get(
    "/stream",
    summary="Subscribe to real-time escalation & ticket-update events (SSE)",
)
async def stream(
    request: Request,
    broker: EventBroker = Broker,
    token: str | None = Query(
        default=None,
        description="Session token (EventSource can't set headers; pass it here).",
    ),
) -> EventSourceResponse:
    # SSE/EventSource can't send Authorization headers, so accept the session
    # token via header OR query param, and scope the stream to that account.
    auth = request.headers.get("authorization")
    raw = (
        auth.split(" ", 1)[1].strip()
        if auth and auth.lower().startswith("bearer ")
        else token
    )
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session token."
        )
    try:
        account_id = decode_session_token(raw)
    except SessionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    async def event_generator() -> AsyncIterator[dict]:
        async with broker.subscribe() as queue:
            # Announce a successful subscription so clients can confirm liveness.
            yield {"event": "connected", "data": json.dumps({"ok": True})}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_KEEPALIVE_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # No event within the window: emit a keepalive comment.
                    yield {"event": "keepalive", "data": "{}"}
                    continue
                # Tenant isolation: only deliver events for this account.
                if event.account_id is not None and event.account_id != account_id:
                    continue
                yield {
                    "event": event.type,
                    "data": json.dumps(event.data, default=str),
                }

    return EventSourceResponse(event_generator())
