"""OAuth provider abstraction.

A *provider* encapsulates everything channel-specific about connecting an account
and sending through it: building the authorize URL, exchanging the auth code for
tokens, fetching the user's identity, and sending a reply. Concrete providers
(Google, Discord, Slack) implement this interface; the rest of the app is written
against the abstraction and a small registry, so adding a channel is localized
and tests can register a stub provider.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProviderTokens:
    """OAuth material returned by a token exchange/refresh."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderIdentity:
    """Who the connecting user is at the provider, plus inbound routing key."""

    provider_user_id: str
    email: str | None = None
    display_name: str | None = None
    # Key used to map inbound platform events back to this connection/account
    # (mailbox address, Discord guild id, Slack team id, ...).
    external_ref: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Raised when a provider call fails (network, non-2xx, bad payload)."""


class OAuthProvider(abc.ABC):
    """Interface every channel provider implements."""

    name: str

    @abc.abstractmethod
    def authorize_url(self, state: str) -> str:
        """Return the provider URL to redirect the user to for consent."""

    @abc.abstractmethod
    async def exchange_code(self, code: str) -> ProviderTokens:
        """Exchange an authorization code for tokens."""

    @abc.abstractmethod
    async def fetch_identity(self, tokens: ProviderTokens) -> ProviderIdentity:
        """Fetch the connecting user's identity using the access token."""

    @abc.abstractmethod
    async def send_message(
        self,
        *,
        tokens: ProviderTokens,
        channel_id: str,
        text: str,
        to_contact: str | None = None,
    ) -> None:
        """Send a reply through this channel on the account's behalf."""

    async def refresh(self, refresh_token: str) -> ProviderTokens:  # optional
        """Refresh an expired access token. Override where supported."""
        raise NotImplementedError(f"{self.name} does not support token refresh.")


# --- Registry -------------------------------------------------------------
_registry: dict[str, OAuthProvider] = {}


def register_provider(provider: OAuthProvider) -> None:
    """Register (or override) a provider by its ``name``."""
    _registry[provider.name] = provider


def get_provider(name: str) -> OAuthProvider:
    """Look up a registered provider, raising ``KeyError`` if unknown."""
    key = name.lower()
    if key not in _registry:
        raise KeyError(f"Unknown or unconfigured provider: {name!r}")
    return _registry[key]


def available_providers() -> list[str]:
    """Names of all registered providers."""
    return sorted(_registry)
