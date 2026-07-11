"""Slack OAuth provider.

Uses OAuth v2. The token exchange returns a bot token plus the team (workspace)
id, which is the inbound routing key (``external_ref``). Sending uses
``chat.postMessage`` with the bot token.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.providers.base import (
    OAuthProvider,
    ProviderError,
    ProviderIdentity,
    ProviderTokens,
)

_AUTH_URL = "https://slack.com/oauth/v2/authorize"
_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


class SlackProvider(OAuthProvider):
    name = "slack"

    def authorize_url(self, state: str) -> str:
        params = {
            "client_id": settings.slack_client_id,
            "scope": settings.slack_scopes,
            "redirect_uri": settings.oauth_redirect_uri(self.name),
            "state": state,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> ProviderTokens:
        data = {
            "client_id": settings.slack_client_id,
            "client_secret": settings.slack_client_secret,
            "code": code,
            "redirect_uri": settings.oauth_redirect_uri(self.name),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(_TOKEN_URL, data=data)
        payload = resp.json()
        if not payload.get("ok"):
            raise ProviderError(f"Slack token exchange failed: {payload}")
        access_token = payload.get("access_token") or payload.get(
            "authed_user", {}
        ).get("access_token")
        return ProviderTokens(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            scopes=payload.get("scope"),
            raw=payload,
        )

    async def fetch_identity(self, tokens: ProviderTokens) -> ProviderIdentity:
        payload = tokens.raw
        team = payload.get("team", {}) or {}
        authed_user = payload.get("authed_user", {}) or {}
        team_id = team.get("id")
        return ProviderIdentity(
            provider_user_id=str(authed_user.get("id") or team_id or ""),
            email=None,
            display_name=team.get("name"),
            external_ref=team_id,  # workspace id is the inbound routing key
            raw=payload,
        )

    async def send_message(
        self,
        *,
        tokens: ProviderTokens,
        channel_id: str,
        text: str,
        to_contact: str | None = None,
    ) -> None:
        if not channel_id:
            raise ProviderError("Slack send requires a channel_id.")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                _POST_MESSAGE_URL,
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json={"channel": channel_id, "text": text},
            )
        data = resp.json()
        if not data.get("ok"):
            raise ProviderError(f"Slack send failed: {data}")
