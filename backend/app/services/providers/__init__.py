"""Provider registry bootstrap.

Registers the real channel providers (Google, Discord, Slack) at import time so
the rest of the app can resolve them via ``get_provider``. Tests may register a
stub provider to exercise the generic OAuth machinery without external calls.
"""

from __future__ import annotations

from app.services.providers.base import (
    OAuthProvider,
    ProviderError,
    ProviderIdentity,
    ProviderTokens,
    available_providers,
    get_provider,
    register_provider,
)
from app.services.providers.discord import DiscordProvider
from app.services.providers.google import GoogleProvider
from app.services.providers.slack import SlackProvider

# Register the built-in real providers.
register_provider(GoogleProvider())
register_provider(DiscordProvider())
register_provider(SlackProvider())

# Map a source channel (as stored on a Ticket) to the provider that sends it.
CHANNEL_TO_PROVIDER = {
    "email": "google",
    "discord": "discord",
    "slack": "slack",
}


def provider_for_channel(channel: str) -> str:
    """Return the provider name responsible for a ticket's source channel."""
    return CHANNEL_TO_PROVIDER.get(channel.lower(), channel.lower())


__all__ = [
    "OAuthProvider",
    "ProviderError",
    "ProviderIdentity",
    "ProviderTokens",
    "available_providers",
    "get_provider",
    "register_provider",
    "provider_for_channel",
    "CHANNEL_TO_PROVIDER",
]
