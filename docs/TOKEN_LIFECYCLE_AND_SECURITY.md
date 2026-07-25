# Token Lifecycle & Security

> The three kinds of tokens in Sentinel, how they're kept apart, how provider
> tokens are encrypted at rest, and how tenants stay isolated. Cross-refs:
> [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md),
> [DISCORD_INTEGRATION.md](./DISCORD_INTEGRATION.md).

## Three token types — never mix them

| Token | Who holds it | What it's for | Lifetime |
| --- | --- | --- | --- |
| **App session JWT** | The **mobile app** (in `expo-secure-store`) | Proves "I am account N" on every backend request (`Authorization: Bearer`). Carries only `account_id`. | ~14 days (`jwt_expires_minutes`) |
| **Provider OAuth tokens** (Google / Discord access + refresh) | The **backend**, encrypted in the DB | Actually *do things* on a channel — read/send Gmail, post Discord. | Access ~1h; refresh long-lived (see below) |
| **Backend API key** | The **workers** (Discord bot, Gmail poller) and any n8n caller | A shared secret guarding `/triage` and `/exchange` from random LAN callers (`X-API-Key`). | Static, set in `.env` |

The golden rule: **the phone never holds a provider OAuth token**, and **the
backend never sends the session JWT to a provider**. Each token stays in its lane.

### Why this separation matters
- If the phone is lost, its JWT expires and grants access only to *that* tenant's
  Sentinel data — never the raw Google/Discord tokens (those live only on the
  server, encrypted).
- The backend is the single confidential party that can exchange codes for tokens
  and decrypt them, which is exactly what Google requires to issue refresh tokens
  (see the Google doc).

## App session JWT

- Minted after a successful OAuth exchange (`app/services/auth.py`
  `create_session_token`), signed with `SENTINEL_JWT_SECRET` (HS256).
- Payload: `sub` = `account_id`, `iat`, `exp`, `typ: "session"`. Nothing sensitive.
- Verified on every tenant-scoped request by the `require_account` dependency
  (`app/api/deps.py`), which loads the `Account` and scopes all queries to it.
- Stored on the device in **SecureStore** (Keychain/Keystore-backed), not plain
  AsyncStorage.

## Provider OAuth tokens — encrypted at rest (Fernet)

Access + refresh tokens are stored in the `channel_connections` table, but
**never in plaintext**. `app/services/crypto.py` wraps **Fernet** (AES-128-CBC +
HMAC-SHA256): the token-store encrypts on write and decrypts on read
transparently.

- **Key source:** `SENTINEL_TOKEN_ENCRYPTION_KEY` (a urlsafe-base64 Fernet key
  from `Fernet.generate_key()`).
- **Dev fallback:** if that env var is empty, a deterministic key is derived from
  `SENTINEL_JWT_SECRET` (SHA-256) so the app runs out-of-the-box.
  > **Production warning:** always set an explicit `SENTINEL_TOKEN_ENCRYPTION_KEY`.
  > With the dev fallback, rotating the JWT secret would change the derived key and
  > make **every stored token undecryptable** (all connections would break).
- **Integrity:** Fernet includes an HMAC, so a tampered or wrong-key ciphertext
  raises `InvalidToken` rather than returning garbage.

## Refresh & rotation

When the backend needs to act on a channel and the **access token is expired**, it
uses the **refresh token** to transparently get a new access token
(`services/connections.py`, used by `services/sender.py` and the workers):

```
need to send/read → is access token expired?
   ├─ no  → use it
   └─ yes → have a refresh token?
             ├─ yes → refresh → store new (encrypted) → use it
             └─ no  → mark connection needs_reconnect  → app shows "Reconnect"
```

- The health flag `needs_reconnect` (computed in `schemas/account.py`) is
  `true` when the access token is expired **and** there's no refresh token to
  renew it. The Channels screen surfaces this with a one-tap reconnect.
- **Google** refresh tokens are only issued under `offlineAccess` + a forced code,
  and expire after 7 days in Testing mode — see the Google doc for the full rules.
- **Discord** user tokens refresh like normal; the **bot token** never expires and
  isn't per-user.

## Backend API key

- `SENTINEL_API_KEY` guards the endpoints that untrusted LAN processes call:
  `/support/triage` (workers/n8n POST here) and `/auth/{provider}/exchange`
  (the app posts OAuth codes here).
- Sent as the `X-API-Key` header. If unset (pure local dev), the check is a
  no-op. Enforced by `require_api_key` in `app/api/deps.py`.
- This is **separate** from the JWT: the API key says "you're an allowed caller of
  this machine"; the JWT says "you are this tenant". Tenant-scoped data endpoints
  (`/tickets`, `/kb/*`, `/me`, …) use the **JWT**, not the API key.

## Multi-tenant isolation (`account_id`)

Every domain row — tickets, channel connections, push tokens, KB documents, KB
chunks — carries an `account_id`. Every query, the SSE stream, push delivery, and
KB retrieval are filtered by the caller's `account_id` (resolved from their JWT).
There is no code path that returns another tenant's data. This is the same pattern
across the whole backend; see [BACKEND_GUIDE.md](./BACKEND_GUIDE.md).

## Secrets checklist (never commit these)

| Secret | Env var | Notes |
| --- | --- | --- |
| JWT signing key | `SENTINEL_JWT_SECRET` | Any long random string. |
| Token encryption key | `SENTINEL_TOKEN_ENCRYPTION_KEY` | `Fernet.generate_key()`. Set explicitly in prod. |
| Backend API key | `SENTINEL_API_KEY` | Shared with workers/n8n. |
| Google Web client secret | `SENTINEL_GOOGLE_CLIENT_SECRET` | Confidential client. |
| Discord client secret + bot token | `SENTINEL_DISCORD_CLIENT_SECRET`, `SENTINEL_DISCORD_BOT_TOKEN` | |
| Firebase service-account key | `mobile/credentials/fcm-service-account.json` | Gitignored; used by EAS, see push doc. |

`backend/.env`, `mobile/.env`, and the FCM key are all gitignored.
