"""Discord community gateway bot (inbound ingestion).

Run as a **separate process** from the FastAPI server:

    python -m app.workers.discord_bot

The bot logs into Discord over the gateway (an outbound WebSocket — no public URL
required) using the application's bot token. It sits in the community servers it
has been invited to and watches a support channel. When a (non-bot) member posts
a message, it forwards a normalized payload to the backend's ``/support/triage``
endpoint, tagged with the **guild id** as ``external_ref`` so the backend maps it
to the owning account. Triage, escalation (SSE) and reply-sending all happen in
the FastAPI process, keeping a single source of truth and one event broker.

Why forward over HTTP instead of triaging in-process? The SSE event broker is an
in-memory singleton living in the FastAPI process; escalations must be published
there to reach connected dashboards. So the bot is inbound-only.

Requirements:
  * ``SENTINEL_DISCORD_BOT_TOKEN`` set in the environment.
  * The **Message Content Intent** enabled for the app in the Discord Developer
    Portal (Bot tab) — otherwise message text arrives empty.
"""

from __future__ import annotations

import logging

import discord
import httpx

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sentinel.discord")

_TRIAGE_URL = f"{settings.app_base_url}{settings.api_v1_prefix}/support/triage"


def _watches_channel(channel: discord.abc.GuildChannel) -> bool:
    """Whether the configured support-channel filter includes this channel."""
    target = settings.discord_support_channel.strip()
    if not target:
        return True  # watch all text channels
    name = getattr(channel, "name", "") or ""
    return target == str(channel.id) or target.lstrip("#").lower() == name.lower()


async def _forward_to_triage(message: discord.Message) -> None:
    """POST a Discord message to the backend triage endpoint."""
    payload = {
        "channel": "discord",
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "author_name": message.author.display_name,
        "author_contact": str(message.author.id),
        "content": message.content,
        "external_ref": str(message.guild.id) if message.guild else None,
    }
    headers = {}
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(_TRIAGE_URL, json=payload, headers=headers)

    if resp.status_code >= 300:
        log.warning("Triage rejected (%s): %s", resp.status_code, resp.text)
        return
    data = resp.json()
    log.info(
        "Triaged msg %s in guild %s -> %s (crit=%.3f)",
        message.id,
        payload["external_ref"],
        data.get("decision"),
        data.get("criticality_score", 0.0),
    )


class SentinelClient(discord.Client):
    async def on_ready(self) -> None:
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)
        guilds = ", ".join(f"{g.name}({g.id})" for g in self.guilds) or "(none)"
        log.info("Watching guilds: %s", guilds)
        if settings.discord_support_channel:
            log.info("Support-channel filter: %s", settings.discord_support_channel)

    async def on_message(self, message: discord.Message) -> None:
        # Ignore ourselves, other bots, and DMs (community-server model only).
        if message.author.bot or message.guild is None:
            return
        if not message.content.strip():
            return
        if not _watches_channel(message.channel):
            return
        try:
            await _forward_to_triage(message)
        except Exception as exc:  # noqa: BLE001 - keep the bot alive on any error
            log.exception("Failed to forward message %s: %s", message.id, exc)


def build_client() -> SentinelClient:
    intents = discord.Intents.default()
    intents.message_content = True  # privileged: enable in the Developer Portal
    intents.guilds = True
    return SentinelClient(intents=intents)


def main() -> None:
    token = settings.discord_bot_token.strip()
    if not token:
        raise SystemExit(
            "SENTINEL_DISCORD_BOT_TOKEN is not set. Add the bot token to the "
            "backend .env (Discord Developer Portal -> Bot -> Reset Token)."
        )
    client = build_client()
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
