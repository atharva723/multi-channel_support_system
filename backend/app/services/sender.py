"""Per-account reply sending.

Replaces the single-tenant n8n dispatch as the primary send path: when an agent
approves/edits a reply, we look up *that account's* connected provider for the
ticket's channel, decrypt its tokens, refresh if needed, and send through the
provider (Gmail / Discord / Slack). If the account has no suitable connection but
a legacy n8n webhook is configured, we fall back to it so nothing silently drops.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.support import Ticket
from app.services import connections as conn_store
from app.services.dispatch import dispatch_reply, is_dispatch_enabled
from app.services.providers import ProviderError, get_provider, provider_for_channel


class SendError(RuntimeError):
    """Raised when an approved reply could not be sent through any path."""


async def send_reply(db: AsyncSession, *, account_id: int, ticket: Ticket) -> str:
    """Send a ticket's current reply for an account. Returns the path used.

    Path is ``"<provider>"`` for a native provider send or ``"n8n"`` for the
    legacy fallback. Raises :class:`SendError` if neither path can deliver.
    """
    provider_name = provider_for_channel(ticket.channel)
    connection = await conn_store.get_connection(
        db, account_id=account_id, provider=provider_name
    )

    if connection is not None:
        try:
            provider = get_provider(provider_name)
        except KeyError as exc:
            raise SendError(str(exc)) from exc

        tokens = conn_store.load_tokens(connection)
        if conn_store.is_expired(connection) and tokens.refresh_token:
            try:
                tokens = await provider.refresh(tokens.refresh_token)
                conn_store._apply_tokens(  # noqa: SLF001 - internal helper reuse
                    connection,
                    tokens,
                    _identity_from_connection(connection),
                )
                await db.commit()
            except (ProviderError, NotImplementedError):
                # Best effort: try sending with the existing token anyway.
                tokens = conn_store.load_tokens(connection)

        try:
            await provider.send_message(
                tokens=tokens,
                channel_id=ticket.channel_id,
                text=ticket.ai_draft_reply or "",
                to_contact=ticket.author_contact,
            )
            return provider_name
        except ProviderError as exc:
            raise SendError(f"{provider_name} send failed: {exc}") from exc

    # No native connection: fall back to n8n if configured.
    if is_dispatch_enabled():
        await dispatch_reply(ticket)
        return "n8n"

    raise SendError(
        f"Account {account_id} has no '{provider_name}' connection and no n8n "
        "fallback configured; cannot send the reply."
    )


def _identity_from_connection(connection):
    """Build a minimal identity to re-apply refreshed tokens without losing meta."""
    from app.services.providers import ProviderIdentity

    return ProviderIdentity(
        provider_user_id=connection.provider_user_id,
        email=connection.email,
        display_name=connection.display_name,
        external_ref=connection.external_ref,
    )
