"""Per-account reply sending.

When an agent approves/edits a reply (or a non-critical ticket is auto-replied),
we look up *that account's* connected provider for the ticket's channel, decrypt
its tokens, refresh if needed, and send through the provider (Gmail / Discord).
Each account sends with its own credentials — there is no shared send path.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support import Ticket
from app.services import connections as conn_store
from app.services.providers import ProviderError, get_provider, provider_for_channel


class SendError(RuntimeError):
    """Raised when an approved reply could not be sent."""


async def send_reply(db: AsyncSession, *, account_id: int, ticket: Ticket) -> str:
    """Send a ticket's current reply for an account. Returns the provider used.

    Raises :class:`SendError` if the account has no connection able to deliver.
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

    raise SendError(
        f"Account {account_id} has no '{provider_name}' connection; "
        "cannot send the reply."
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
