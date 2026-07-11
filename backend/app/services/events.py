"""In-process real-time event broker.

Phase 2 needs a way for the triage pipeline (and ticket mutations) to push
updates to any number of connected mobile dashboards *immediately*, without the
client polling. This module is a lightweight publish/subscribe hub built on
``asyncio.Queue``:

  * The SSE endpoint calls :meth:`EventBroker.subscribe` to get its own queue and
    async-iterates it for the life of the connection.
  * Producers (the triage endpoint on escalation, the tickets endpoint on a
    status change) call :meth:`EventBroker.publish`, which fans the event out to
    every subscriber's queue.

It is intentionally in-memory and single-process: perfect for one FastAPI worker
driving the dashboard. Scaling to multiple workers would swap this implementation
for Redis pub/sub behind the same interface — the rest of the app is unaffected.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Bounded so a slow/dead client cannot grow memory unboundedly; when full we
# drop the oldest event for that subscriber rather than blocking producers.
_SUBSCRIBER_QUEUE_MAXSIZE = 100


@dataclass
class Event:
    """A single real-time event delivered over SSE."""

    type: str  # e.g. "escalation", "ticket_update"
    data: dict[str, Any]
    account_id: int | None = None  # tenant scope; subscribers filter on this
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class EventBroker:
    """Fan-out hub delivering events to all active SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        """Deliver ``event`` to every current subscriber (non-blocking)."""
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest event to make room for the newest.
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Event]]:
        """Register a subscriber queue for the duration of a connection."""
        queue: asyncio.Queue[Event] = asyncio.Queue(
            maxsize=_SUBSCRIBER_QUEUE_MAXSIZE
        )
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        """Number of currently connected subscribers."""
        return len(self._subscribers)


# Process-wide singleton.
_broker: EventBroker | None = None


def get_event_broker() -> EventBroker:
    """Return the process-wide ``EventBroker`` singleton."""
    global _broker
    if _broker is None:
        _broker = EventBroker()
    return _broker
