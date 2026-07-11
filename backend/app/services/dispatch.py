"""Outbound reply dispatch.

When a human agent approves (or edits and approves) a draft on the mobile
Escalation Desk, the reply still has to physically leave through the channel the
customer used — Discord, Slack, or email. Those send credentials live in n8n
(not the backend or the mobile client), so the backend "dispatches" the approved
reply by POSTing it to an n8n webhook (the *Reply Dispatcher* workflow), which
routes it to the right platform.

This keeps a clean separation: the backend owns triage + state, n8n owns all
platform I/O. Dispatch is optional — if ``n8n_reply_webhook_url`` is unset (e.g.
local dev before n8n is wired up), the caller simply skips sending.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.models.support import Ticket


class DispatchError(RuntimeError):
    """Raised when the reply could not be handed off to n8n for sending."""


def is_dispatch_enabled() -> bool:
    """True when an n8n reply webhook is configured."""
    return bool(settings.n8n_reply_webhook_url)


async def dispatch_reply(ticket: Ticket) -> None:
    """POST an approved reply to the n8n Reply Dispatcher webhook.

    No-op when dispatch is disabled. Raises ``DispatchError`` on transport or
    non-2xx responses so the caller can surface the failure instead of silently
    marking a reply "sent" that never left.
    """
    if not is_dispatch_enabled():
        return

    payload = {
        "ticket_id": ticket.id,
        "channel": ticket.channel,
        "channel_id": ticket.channel_id,
        "author_name": ticket.author_name,
        "author_contact": ticket.author_contact,
        "reply_text": ticket.ai_draft_reply or "",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.n8n_dispatch_timeout) as client:
            resp = await client.post(settings.n8n_reply_webhook_url, json=payload)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise DispatchError(
            f"n8n dispatcher returned HTTP {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise DispatchError(f"Could not reach n8n dispatcher: {exc}") from exc
