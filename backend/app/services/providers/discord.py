"""Discord OAuth provider.

Identity via the OAuth2 ``users/@me`` endpoint. Sending uses the application's
**bot token** (user OAuth tokens can't post arbitrary channel messages), posting
to ``channels/{channel_id}/messages``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.providers.base import (
    OAuthProvider,
    ProviderError,
    ProviderIdentity,
    ProviderTokens,
)

_API = "https://discord.com/api"
_AUTH_URL = "https://discord.com/oauth2/authorize"
_TOKEN_URL = f"{_API}/oauth2/token"
_ME_URL = f"{_API}/users/@me"


class DiscordProvider(OAuthProvider):
    name = "discord"

    def authorize_url(self, state: str) -> str:
        params = {
            "client_id": settings.discord_client_id,
            "redirect_uri": settings.oauth_redirect_uri(self.name),
            "response_type": "code",
            "scope": settings.discord_scopes,
            "state": state,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> ProviderTokens:
        data = {
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri(self.name),
        }
        payload = await self._post_form(_TOKEN_URL, data)
        return self._tokens_from_payload(payload)

    async def exchange_code_pkce(
        self, code: str, code_verifier: str, redirect_uri: str
    ) -> ProviderTokens:
        # App-owned redirect (sentinel://oauthredirect) + PKCE verifier. Discord
        # is a confidential client so the secret is still sent server-side here.
        data = {
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        payload = await self._post_form(_TOKEN_URL, data)
        return self._tokens_from_payload(payload)

    async def refresh(self, refresh_token: str) -> ProviderTokens:
        data = {
            "client_id": settings.discord_client_id,
            "client_secret": settings.discord_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        payload = await self._post_form(_TOKEN_URL, data)
        return self._tokens_from_payload(payload)

    async def fetch_identity(self, tokens: ProviderTokens) -> ProviderIdentity:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                _ME_URL,
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
        if resp.status_code != 200:
            raise ProviderError(f"Discord identity failed: {resp.status_code} {resp.text}")
        data = resp.json()
        username = data.get("global_name") or data.get("username")
        return ProviderIdentity(
            provider_user_id=str(data.get("id")),
            email=data.get("email"),
            display_name=username,
            external_ref=str(data.get("id")),
            raw=data,
        )

    async def send_message(
        self,
        *,
        tokens: ProviderTokens,
        channel_id: str,
        text: str,
        to_contact: str | None = None,
    ) -> None:
        if not settings.discord_bot_token:
            raise ProviderError("Discord send requires SENTINEL_DISCORD_BOT_TOKEN.")
        if not channel_id:
            raise ProviderError("Discord send requires a channel_id.")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{_API}/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {settings.discord_bot_token}"},
                json={"content": text},
            )
        if resp.status_code >= 300:
            raise ProviderError(f"Discord send failed: {resp.status_code} {resp.text}")

    # -- helpers -----------------------------------------------------------
    @staticmethod
    async def _post_form(url: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            raise ProviderError(f"Discord token call failed: {resp.status_code} {resp.text}")
        return resp.json()

    @staticmethod
    def _tokens_from_payload(payload: dict) -> ProviderTokens:
        expires_in = payload.get("expires_in")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            if expires_in
            else None
        )
        return ProviderTokens(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scopes=payload.get("scope"),
            raw=payload,
        )
