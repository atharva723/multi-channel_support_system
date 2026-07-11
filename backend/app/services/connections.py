"""Channel connections & token store.

Bridges OAuth providers and the tenancy model. Responsibilities:

  * On connect, upsert a :class:`ChannelConnection` and, when it's a brand-new
    identity, create the owning :class:`Account` (that's how sign-up happens).
    When an already-authenticated user connects an additional provider, the new
    connection is linked to their existing account.
  * Encrypt provider tokens on write, decrypt on read (never plaintext at rest).
  * Resolve inbound platform events back to an account via ``external_ref``.
  * Provide the decrypted tokens used to actually send a reply.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account, ChannelConnection
from app.services.crypto import decrypt, encrypt
from app.services.providers import ProviderIdentity, ProviderTokens


async def connect_provider(
    db: AsyncSession,
    *,
    provider: str,
    tokens: ProviderTokens,
    identity: ProviderIdentity,
    link_account_id: int | None = None,
) -> tuple[Account, ChannelConnection, bool]:
    """Create/refresh a connection; create the account on first sign-up.

    Returns ``(account, connection, created_account)``.

    * If the (provider, provider_user_id) already exists -> update its tokens and
      return its account (this is a returning sign-in).
    * Else if ``link_account_id`` is given -> attach a new connection to that
      existing account (authenticated user adding a channel).
    * Else -> create a new account (fresh sign-up) plus the connection.
    """
    existing = await db.scalar(
        select(ChannelConnection).where(
            ChannelConnection.provider == provider,
            ChannelConnection.provider_user_id == identity.provider_user_id,
        )
    )
    if existing is not None:
        _apply_tokens(existing, tokens, identity)
        await db.commit()
        await db.refresh(existing)
        account = await db.get(Account, existing.account_id)
        return account, existing, False

    created_account = False
    if link_account_id is not None:
        account = await db.get(Account, link_account_id)
        if account is None:
            raise ValueError(f"Account {link_account_id} not found for linking.")
    else:
        account = Account(
            display_name=identity.display_name or identity.email or f"{provider} user",
            email=identity.email,
        )
        db.add(account)
        await db.flush()  # assign account.id
        created_account = True

    connection = ChannelConnection(
        account_id=account.id,
        provider=provider,
        provider_user_id=identity.provider_user_id,
    )
    _apply_tokens(connection, tokens, identity)
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    await db.refresh(account)
    return account, connection, created_account


def _apply_tokens(
    conn: ChannelConnection,
    tokens: ProviderTokens,
    identity: ProviderIdentity,
) -> None:
    """Copy identity + encrypted tokens onto a connection row."""
    conn.display_name = identity.display_name or conn.display_name
    conn.email = identity.email or conn.email
    conn.external_ref = identity.external_ref or conn.external_ref
    conn.access_token_enc = encrypt(tokens.access_token)
    conn.refresh_token_enc = (
        encrypt(tokens.refresh_token) if tokens.refresh_token else None
    )
    conn.scopes = tokens.scopes
    conn.token_expires_at = tokens.expires_at


def load_tokens(conn: ChannelConnection) -> ProviderTokens:
    """Decrypt a connection's stored tokens for use in a provider call."""
    return ProviderTokens(
        access_token=decrypt(conn.access_token_enc),
        refresh_token=decrypt(conn.refresh_token_enc) if conn.refresh_token_enc else None,
        expires_at=conn.token_expires_at,
        scopes=conn.scopes,
    )


def is_expired(conn: ChannelConnection) -> bool:
    """True if the stored access token is known to be expired."""
    if conn.token_expires_at is None:
        return False
    exp = conn.token_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= datetime.now(timezone.utc)


async def list_connections(
    db: AsyncSession, account_id: int
) -> list[ChannelConnection]:
    """All connections for an account."""
    rows = await db.scalars(
        select(ChannelConnection)
        .where(ChannelConnection.account_id == account_id)
        .order_by(ChannelConnection.created_at)
    )
    return list(rows.all())


async def get_connection(
    db: AsyncSession, *, account_id: int, provider: str
) -> ChannelConnection | None:
    """Fetch a specific account's connection for a provider."""
    return await db.scalar(
        select(ChannelConnection).where(
            ChannelConnection.account_id == account_id,
            ChannelConnection.provider == provider,
        )
    )


async def resolve_account_by_external_ref(
    db: AsyncSession, *, provider: str, external_ref: str
) -> int | None:
    """Map an inbound platform event to its owning account id."""
    conn = await db.scalar(
        select(ChannelConnection).where(
            ChannelConnection.provider == provider,
            ChannelConnection.external_ref == external_ref,
        )
    )
    return conn.account_id if conn else None


async def delete_connection(
    db: AsyncSession, *, account_id: int, connection_id: int
) -> bool:
    """Remove a connection owned by an account. Returns True if deleted."""
    conn = await db.get(ChannelConnection, connection_id)
    if conn is None or conn.account_id != account_id:
        return False
    await db.delete(conn)
    await db.commit()
    return True
