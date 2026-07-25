# Discord Integration

> How Sentinel signs users in with Discord (PKCE), listens for community support
> messages (gateway bot), and posts replies back. See also
> [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md) and
> [TOKEN_LIFECYCLE_AND_SECURITY.md](./TOKEN_LIFECYCLE_AND_SECURITY.md).

## Two completely different Discord "auth" things

The biggest gotcha: Discord has **two separate authentication models**, and this
project uses **both** for different jobs. They are not interchangeable.

| Thing | What it is | Used for | Where it lives |
| --- | --- | --- | --- |
| **OAuth2 Client ID + Secret** | Identifies your *application*; used in the user-login (PKCE) flow. | **Sign-in / identity** — the user authorizes Sentinel and we learn who they are + which servers (guilds) they're in. | Backend `.env` (`discord_client_id` / `discord_client_secret`); client ID also in mobile `.env`. |
| **Bot token** | A permanent credential for a *bot user* that lives in servers. | **Reading messages** (gateway listener) and **sending replies** (posting to a channel). | Backend `.env` (`discord_bot_token`). |

> **Why both?** A user's OAuth token can identify them and list their guilds, but
> it **cannot read channel messages or post as a bot**. Only the **bot** (with its
> token, added to the server) can listen to and reply in channels. So OAuth = "who
> is this user + which server is theirs", bot = "actually watch and reply in that
> server".

## Sign-in flow — Authorization Code + PKCE

Discord cleanly supports a **custom-scheme redirect**, so the app owns the
redirect (no backend public URL needed):

```
[App]  build auth URL with PKCE, redirect_uri = sentinel://oauthredirect
[App]  promptAsync()  → Discord consent screen
[User] approves  → Discord redirects to  sentinel://oauthredirect?code=...   (lands IN the app)
        │
        │  POST /api/v1/auth/discord/exchange { code, code_verifier, redirect_uri }  (+ Bearer to link)
        ▼
[Backend]  exchange code + client_secret + code_verifier → tokens
           fetch identity (users/@me) → store encrypted, upsert Account, mint JWT
        │
        ▼
[App]  stores session JWT → signed in
```

- **PKCE** (Proof Key for Code Exchange) protects the code in transit: the app
  generates a random `code_verifier`, sends its hash up front, and reveals the
  verifier only at exchange time. Even though Discord is a confidential client (we
  also send the secret from the backend), PKCE is used because the redirect lands
  on the device.
- Implementation: `mobile/src/lib/oauth.ts` (`connectDiscord`, using
  `expo-auth-session`) + backend `app/services/providers/discord.py`
  (`exchange_code_pkce`).

### The fixed redirect URI — register it once
In the [Discord Developer Portal](https://discord.com/developers/applications) →
your app → **OAuth2 → Redirects**, add exactly:

```
sentinel://oauthredirect
```

> **Why a fixed custom scheme is a big deal:** with a normal web redirect you'd
> have to re-register the URL every time your backend's public address changed
> (e.g. a new tunnel URL each run). A custom scheme (`sentinel://`) belongs to the
> **app**, not a server, so it **never changes** — register it once, forever. This
> is the core reason the project moved to app-owned OAuth ("Option B"). It also
> requires a **custom dev build** (Expo Go can't own `sentinel://`) — see
> [MOBILE_APP_GUIDE.md](./MOBILE_APP_GUIDE.md).

OAuth scopes requested: `identify email guilds` (`discord_scopes` in config).

## Inbound: the gateway bot listener

`backend/app/workers/discord_bot.py` runs a **`discord.py` gateway bot**. It
connects to Discord's real-time gateway and fires on every new message in servers
the bot is in, then POSTs each message to `/triage` with the **guild id** as the
`external_ref` (so the backend resolves the right tenant).

### Gateway Intents (must be enabled)
The bot needs the **Message Content Intent** to read message text. Enable it in
the Developer Portal → your app → **Bot → Privileged Gateway Intents → Message
Content Intent**. Without it, the bot connects but every message body arrives
empty.

Relevant config:
- `discord_support_channel` — name/id of the channel to watch (empty = all text
  channels the bot can see).
- `discord_auto_link_guild` — dev convenience: if an inbound guild isn't linked to
  an account yet and exactly one Discord connection exists, auto-link it. Keep this
  `False` in real multi-tenant production.

### Adding the bot to a server
Generate an invite URL in the portal (**OAuth2 → URL Generator**, scope `bot`,
with "Read Messages/View Channels" + "Send Messages" permissions) and open it to
add the bot to your server. The user then picks which server Sentinel watches via
the app's **Channels → Discord → server picker** (`/connections/discord/guilds` +
`/connections/discord/link-guild`).

## Outbound: replying

Approved/auto replies are sent by the **bot** posting to
`channels/{channel_id}/messages` with the bot token (`discord.py` /
`services/providers/discord.py` → `send_message`). The user's OAuth token is never
used to send — only the bot can.

## Token lifecycle note

Discord user OAuth tokens **do** expire and have refresh tokens (handled like any
provider). The **bot token**, by contrast, is long-lived and non-expiring — it's a
single app-level secret in the backend `.env`, not per-user. See
[TOKEN_LIFECYCLE_AND_SECURITY.md](./TOKEN_LIFECYCLE_AND_SECURITY.md).

## Env vars
```
# backend .env
SENTINEL_DISCORD_CLIENT_ID=<application client id>
SENTINEL_DISCORD_CLIENT_SECRET=<application client secret>
SENTINEL_DISCORD_BOT_TOKEN=<bot token>
# mobile .env
EXPO_PUBLIC_DISCORD_CLIENT_ID=<same application client id>
```
