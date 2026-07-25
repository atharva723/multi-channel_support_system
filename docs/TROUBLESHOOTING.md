# Troubleshooting

> Real issues hit while building/running Sentinel, with the actual fixes. Grouped
> by symptom.

## Setup / connectivity

### The phone can't reach the backend / app shows network errors
The phone talks to your machine over Wi-Fi using its **LAN IP** (e.g.
`192.168.0.102`), which **changes on reboot / network switch**.
- **Fix:** run `scripts/demo-start-lan.ps1` — it auto-detects the current LAN IP
  and writes it into both `backend/.env` (`SENTINEL_APP_BASE_URL`) and
  `mobile/.env` (`EXPO_PUBLIC_API_URL`). Then reload the app.
- Make sure the phone and PC are on the **same Wi-Fi**, and Windows Firewall
  allows inbound on port 8000/8081.

### Workers (bot/poller) can't post to `/triage`
`SENTINEL_APP_BASE_URL` must be the **current LAN IP** (not a stale tunnel URL).
Workers POST to that address. The launcher keeps it in sync; if you started things
manually, set it yourself.

### Ollama errors / `/triage` returns 502
- Ensure Ollama is **running** and the models are pulled:
  `ollama list` should show `llama3.2` and `nomic-embed-text`.
  `ollama pull llama3.2 && ollama pull nomic-embed-text`.
- Check `SENTINEL_OLLAMA_HOST` (default `http://localhost:11434`).

## OAuth

### Google: no refresh token (connection keeps needing reconnect)
Google only issues a refresh token on first consent / with a forced code.
- The app already sets `offlineAccess: true` + `forceCodeForRefreshToken: true`
  and signs out before signing in. If you still get none, **revoke** the app at
  [myaccount.google.com/permissions](https://myaccount.google.com/permissions) and
  reconnect.
- Remember the **7-day** refresh expiry while the consent screen is in Testing
  mode — see [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md).

### Google: sign-in fails on device immediately
The **Android OAuth client** must exist in the same GCP project with the right
**package name** (`com.sentinel.app`) and the build's **SHA-1**
(`npx eas credentials` → Android). And `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` must be
the **Web** client id, not the Android one.

### Discord: "Invalid redirect URI"
`sentinel://oauthredirect` must be registered exactly in the Discord Developer
Portal → OAuth2 → Redirects.

### "Unmatched Route" flash after an OAuth redirect
`WebBrowser.maybeCompleteAuthSession()` must run at module load, and the
`app/oauthredirect.tsx` route must exist. See
[MOBILE_APP_GUIDE.md](./MOBILE_APP_GUIDE.md).

### Connecting a second channel created a new account
The client must send the existing `Bearer` token on `/exchange` to **link**. If a
duplicate account appeared, it was connected without the token.

## Discord bot

### Bot connects but message bodies are empty
Enable the **Message Content Intent** (Developer Portal → Bot → Privileged Gateway
Intents). Without it, `content` arrives blank.

### Messages don't create tickets
- The bot must be **in the server** and able to see the channel.
- The guild must be **linked to an account** (Channels → Discord → pick server),
  or `discord_auto_link_guild` enabled for single-tenant dev.

## Mobile build / Metro

### My code changes don't show up on the phone
Metro must run in **watch mode** (not CI mode). CI mode **disables reloads** and
freezes the bundle. The launcher runs Metro correctly (detached, watch mode). If
edits still don't appear, restart Metro with a cleared cache:
`npx expo start --dev-client --clear`.

### After adding a native module, features crash / don't work
Native modules (Google Sign-In, notifications, document picker) require a **new
EAS build** — JS hot-reloads, native code doesn't. Rebuild and reinstall the APK.

### Terminal floods with escape codes like `[<..M`
That's `expo start` putting the terminal into mouse-reporting mode. The launcher
avoids it by running Metro detached with output redirected. Don't run interactive
`expo start` in the shared terminal.

## Push notifications

### No push arrives on a critical ticket
1. Grant the **notification permission** on first launch.
2. **FCM must be set up:** `google-services.json` baked into the build **and** the
   service-account key uploaded to EAS. Missing either → silent failure. See
   [PUSH_NOTIFICATIONS_FCM.md](./PUSH_NOTIFICATIONS_FCM.md).
3. The token registers after sign-in — make sure you're signed in.
4. Confirm the ticket was actually **critical** (≥ 0.8) — non-critical ones
   auto-reply and don't push.

## Tickets / timestamps

### Timestamps look wrong ("5h ago" for something just now)
The backend serializes `created_at` as **UTC with an explicit offset**, and the
app parses tz-less strings as UTC. If you see skew, you're likely on a stale
bundle — reload (Metro watch mode issue above).

### Inbox ordering looks off
The Inbox sorts newest-first by `id` (monotonic with creation) — robust across JS
engines. The Desk sorts by **aged urgency**, which is intentional (older critical
tickets rise).

## Knowledge base

### Upload/website stuck on "processing"
Embedding runs in the background via Ollama. If it never finishes, check Ollama is
up and `nomic-embed-text` is pulled. A `failed` status shows the error inline.

### A website added but "couldn't extract content"
Some sites block bots or render content purely via JS. The scraper uses a
browser-like User-Agent and `trafilatura`; heavily JS-rendered pages may yield
little text. Try a more content-rich URL (e.g. the FAQ/policy page directly).

### Answers don't reflect a doc I uploaded
- Confirm the doc is **Ready** (not processing/failed).
- The question may be scoring below `kb_min_score` (0.6) → treated as out of
  scope. Rephrase closer to the document's wording, or lower the threshold in
  `config.py`.

## Database

### Added a model column but it's missing at runtime
`create_all` doesn't alter existing tables. Run a one-off
`ALTER TABLE ... ADD COLUMN` on `backend/sentinel.db` (fresh DBs pick it up from
the model). No Alembic yet.
