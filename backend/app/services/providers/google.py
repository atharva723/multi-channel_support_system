"""Google (Gmail) OAuth provider.

Identity via OpenID Connect userinfo; sending via the Gmail API
(``users.messages.send`` with a base64url-encoded RFC 822 message). The connected
mailbox address doubles as the inbound routing key (``external_ref``).
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.providers.base import (
    OAuthProvider,
    ProviderError,
    ProviderIdentity,
    ProviderTokens,
)

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GoogleProvider(OAuthProvider):
    name = "google"

    def authorize_url(self, state: str) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.oauth_redirect_uri(self.name),
            "response_type": "code",
            "scope": settings.google_scopes,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> ProviderTokens:
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.oauth_redirect_uri(self.name),
            "grant_type": "authorization_code",
        }
        payload = await self._post_form(_TOKEN_URL, data)
        return self._tokens_from_payload(payload)

    async def exchange_server_auth_code(self, code: str) -> ProviderTokens:
        # Native Google Sign-In (offlineAccess) returns a serverAuthCode that the
        # backend swaps using the WEB client id+secret. No redirect_uri is used
        # for this grant; with offline access Google returns a refresh token.
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": "",
        }
        payload = await self._post_form(_TOKEN_URL, data)
        return self._tokens_from_payload(payload)

    async def refresh(self, refresh_token: str) -> ProviderTokens:
        data = {
            "refresh_token": refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "grant_type": "refresh_token",
        }
        payload = await self._post_form(_TOKEN_URL, data)
        tokens = self._tokens_from_payload(payload)
        if tokens.refresh_token is None:
            tokens.refresh_token = refresh_token  # Google omits it on refresh
        return tokens

    async def fetch_identity(self, tokens: ProviderTokens) -> ProviderIdentity:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                _USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
        if resp.status_code != 200:
            raise ProviderError(f"Google userinfo failed: {resp.status_code} {resp.text}")
        data = resp.json()
        email = data.get("email")
        return ProviderIdentity(
            provider_user_id=str(data.get("sub")),
            email=email,
            display_name=data.get("name") or email,
            external_ref=email,  # the mailbox is the inbound routing key
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
        if not to_contact:
            raise ProviderError("Gmail send requires a recipient (to_contact).")
        msg = EmailMessage()
        msg["To"] = to_contact
        msg["Subject"] = "Re: your support request"
        msg.set_content(text)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                _GMAIL_SEND_URL,
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json={"raw": raw},
            )
        if resp.status_code >= 300:
            raise ProviderError(f"Gmail send failed: {resp.status_code} {resp.text}")

    async def list_new_messages(
        self, tokens: ProviderTokens, *, after_epoch: int | None = None, max_results: int = 10
    ) -> list[dict]:
        """Fetch recent inbox messages, newest first, parsed for triage.

        Returns a list of dicts: {message_id, thread_id, from_name, from_email,
        subject, body, internal_ts}. ``after_epoch`` (unix seconds) limits to
        messages newer than the last poll using Gmail's ``after:`` query.
        """
        headers = {"Authorization": f"Bearer {tokens.access_token}"}
        q = "in:inbox -from:me"
        if after_epoch:
            q += f" after:{after_epoch}"
        async with httpx.AsyncClient(timeout=25) as client:
            listing = await client.get(
                f"{_GMAIL_BASE}/messages",
                headers=headers,
                params={"q": q, "maxResults": max_results},
            )
            if listing.status_code != 200:
                raise ProviderError(
                    f"Gmail list failed: {listing.status_code} {listing.text}"
                )
            ids = [m["id"] for m in listing.json().get("messages", [])]

            out: list[dict] = []
            for mid in ids:
                detail = await client.get(
                    f"{_GMAIL_BASE}/messages/{mid}",
                    headers=headers,
                    params={"format": "full"},
                )
                if detail.status_code != 200:
                    continue
                out.append(self._parse_message(detail.json()))
        return out

    @staticmethod
    def _parse_message(msg: dict) -> dict:
        """Extract sender, subject, and plain-text body from a Gmail message."""
        payload = msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        raw_from = headers.get("from", "")
        # "Name <email>" -> split.
        from_name, from_email = raw_from, raw_from
        if "<" in raw_from and ">" in raw_from:
            from_name = raw_from.split("<")[0].strip().strip('"')
            from_email = raw_from.split("<")[1].split(">")[0].strip()

        body = GoogleProvider._extract_body(payload) or msg.get("snippet", "")
        return {
            "message_id": msg.get("id"),
            "thread_id": msg.get("threadId"),
            "from_name": from_name or from_email,
            "from_email": from_email,
            "subject": headers.get("subject", "(no subject)"),
            "body": body.strip(),
            "internal_ts": int(msg.get("internalDate", "0")) // 1000,
        }

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Recursively pull the text/plain part of a Gmail payload."""
        mime = payload.get("mimeType", "")
        data = payload.get("body", {}).get("data")
        if mime == "text/plain" and data:
            return base64.urlsafe_b64decode(data + "===").decode("utf-8", "ignore")
        for part in payload.get("parts", []) or []:
            found = GoogleProvider._extract_body(part)
            if found:
                return found
        # Fallback to html stripped-ish if no plain part.
        if mime == "text/html" and data:
            html = base64.urlsafe_b64decode(data + "===").decode("utf-8", "ignore")
            return re.sub(r"<[^>]+>", " ", html)
        return ""

    # -- helpers -----------------------------------------------------------
    @staticmethod
    async def _post_form(url: str, data: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, data=data)
        if resp.status_code != 200:
            raise ProviderError(f"Google token call failed: {resp.status_code} {resp.text}")
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
