"""Application configuration.

Central, typed settings loaded from environment variables (and an optional
``.env`` file) via ``pydantic-settings``. Every later feature — triage, urgency
scoring, the LLM router and the SSE gateway — reads its knobs from here so there
is a single source of truth for tuning.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Sentinel backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SENTINEL_",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    app_name: str = "Omnichannel AI Support Sentinel"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    # Public base URL of this backend, used to build OAuth redirect URIs.
    app_base_url: str = "http://localhost:8000"
    # Where to send the user after a successful OAuth connect (the mobile app can
    # intercept this deep link / URL to capture the issued session token).
    oauth_success_redirect: str = "sentinel://auth/success"

    # --- Database ----------------------------------------------------------
    # Async SQLite driver. The file lives at backend/sentinel.db by default.
    database_url: str = "sqlite+aiosqlite:///./sentinel.db"

    # --- LLM Router (Ollama) ----------------------------------------------
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    # Request timeout (seconds) for classification/draft calls.
    ollama_timeout: float = 60.0
    # Number of alternative tokens to request when computing classification
    # log-probabilities. Must be large enough that both class tokens ("Critical"
    # and "Informational") reliably appear in the returned distribution.
    llm_top_logprobs: int = 20
    # Sampling temperature for the draft-reply generation call (0 for classify).
    llm_reply_temperature: float = 0.4
    # Max tokens for a generated draft reply.
    llm_reply_max_tokens: int = 220

    # --- Triage thresholds -------------------------------------------------
    # If P(C=1|M) >= this threshold the ticket is escalated to the mobile app;
    # otherwise the auto-response engine drafts a reply.
    criticality_threshold: float = 0.8

    # --- SLA urgency: U(t) = S0 * exp(lambda_c * t) ------------------------
    # S0 (initial severity index) is derived from the criticality probability
    # scaled by this factor, so a fresh critical ticket already ranks high and
    # then grows with wait time.
    severity_scale: float = 10.0
    # Per-channel decay/priority constants (lambda_c). Higher => urgency grows
    # faster with wait time. Defaults are sensible starting points; tune per SLA.
    lambda_discord: float = 0.05  # high conversational expectations
    lambda_slack: float = 0.03  # business conversational expectations
    lambda_email: float = 0.01  # standard asynchronous expectations

    # --- API security ------------------------------------------------------
    # Optional shared secret. When set, requests to protected endpoints (e.g.
    # /support/triage called by n8n) must send it via the X-API-Key header.
    # Leave empty to disable auth (local development).
    api_key: str = ""

    # --- Outbound reply dispatch (backend -> n8n) --------------------------
    # When an agent approves/modifies a reply, the backend POSTs it to this n8n
    # webhook, which owns the Discord/Slack/SMTP send credentials. Leave empty
    # to disable dispatch (status is still updated; nothing is sent).
    # Typically: http://localhost:5678/webhook/send-reply
    n8n_reply_webhook_url: str = ""
    # Timeout (seconds) for the dispatch call to n8n.
    n8n_dispatch_timeout: float = 15.0

    # --- Auth / sessions (JWT) --------------------------------------------
    # Secret used to sign app session JWTs. MUST be overridden in production.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 14  # 14 days

    # --- Token encryption at rest -----------------------------------------
    # Urlsafe base64 32-byte Fernet key encrypting provider OAuth tokens in the
    # DB. If blank, a key is derived from jwt_secret (dev only; set explicitly in
    # production so rotating the JWT secret doesn't orphan stored tokens).
    token_encryption_key: str = ""

    # --- OAuth providers (identity + send authorization) ------------------
    # A provider connection is BOTH how a user signs in and the authorization
    # used to send replies through that channel. Fill client id/secret per
    # provider from its developer console; scopes have sensible defaults.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_scopes: str = (
        "openid email profile https://www.googleapis.com/auth/gmail.send "
        "https://www.googleapis.com/auth/gmail.readonly"
    )

    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_bot_token: str = ""  # for sending via the bot, if used
    discord_scopes: str = "identify email guilds"

    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_scopes: str = "chat:write,channels:history,users:read"

    def lambda_for_channel(self, channel: str) -> float:
        """Return the decay constant lambda_c for a given source channel."""
        return {
            "discord": self.lambda_discord,
            "slack": self.lambda_slack,
            "email": self.lambda_email,
        }.get(channel.lower(), self.lambda_email)

    def oauth_redirect_uri(self, provider: str) -> str:
        """Build the OAuth callback URL this backend exposes for a provider."""
        return f"{self.app_base_url}{self.api_v1_prefix}/auth/{provider}/callback"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()


settings = get_settings()
