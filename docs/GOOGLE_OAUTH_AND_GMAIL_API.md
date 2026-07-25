# Google OAuth & Gmail API

> How this project signs users in with Google, reads their Gmail, and sends
> replies as them — plus the hard-won GCP facts that aren't obvious until you've
> hit them. See also [TOKEN_LIFECYCLE_AND_SECURITY.md](./TOKEN_LIFECYCLE_AND_SECURITY.md)
> and [DISCORD_INTEGRATION.md](./DISCORD_INTEGRATION.md).

## What Google is used for here

1. **Sign-in / identity** — connecting Google *is* how a user creates or logs
   into their Sentinel account (there are no passwords).
2. **Gmail read** — the Gmail poller reads new support emails (`gmail.readonly`).
3. **Gmail send** — approved replies are sent **as the user** (`gmail.send`).

All three come from a single Google OAuth connection whose tokens are stored
encrypted per account.

## The OAuth Consent Screen (do this first)

In [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services →
OAuth consent screen**:

- **User type: External** (unless everyone is in one Google Workspace org).
- Add the **scopes** this app uses (below).
- Add your own Google account under **Test users**.

> **Testing-mode cap (important):** while the consent screen is in "Testing"
> status, only **up to 100 named test users** can authorize the app, and their
> refresh tokens expire after **7 days**. To lift both limits you must **publish**
> the app and — because Gmail scopes are "restricted" — pass **Google's
> verification/security review**. For a demo or internal tool, staying in Testing
> with yourself as a test user is fine; just know the 7-day refresh expiry is why
> a connection can suddenly need reconnecting.

## Gmail API scopes used

From `backend/app/core/config.py` (`google_scopes`):

```
openid email profile
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/gmail.readonly
```

- `openid email profile` — identity (who the user is).
- `gmail.readonly` — the poller lists + reads inbound messages.
- `gmail.send` — send the approved reply as the user.

`gmail.send` and `gmail.readonly` are **restricted scopes** → they trigger the
verification requirement above once you publish.

## Two OAuth client IDs — and why you need *both*

This is the single most confusing part of Google OAuth on mobile. You create
**two different OAuth client IDs** in **Credentials → Create OAuth client ID**:

| Client type | Where it's used | Why |
| --- | --- | --- |
| **Web application** | On the **backend** (`google_client_id` / `google_client_secret`) and as the app's `webClientId`. | Google only issues a **refresh token** to a *confidential* (web) client that holds a secret and does the code exchange server-side. The backend is that confidential client. |
| **Android** | Nowhere in code — it just has to **exist** in the same GCP project, matching your app's **package name** (`com.sentinel.app`) + the build's **SHA-1**. | The native Google Sign-In SDK on the phone validates against it invisibly. Without it, `signIn()` fails on-device. |

> **Key mental model:** the **Android** client authenticates the *device*; the
> **Web** client is what actually receives the `serverAuthCode` and is exchanged
> (with the secret) for tokens. In `mobile/.env`,
> `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` is the **Web** client ID — never the Android
> one.

### Registering the Android client
Credentials → Create OAuth client ID → **Android**:
- **Package name:** `com.sentinel.app`
- **SHA-1:** from your EAS build keystore — `npx eas credentials` → Android →
  read the SHA-1 fingerprint. (This is the EAS-managed keystore's fingerprint,
  not a local debug key.)

## The flow this project uses ("Option B", app-owned)

Instead of the classic web redirect (which needs a fixed public backend URL /
tunnel), the app performs Google Sign-In **natively** and hands the backend a
one-time code:

```
[App]  GoogleSignin.configure({ webClientId, offlineAccess: true,
                                forceCodeForRefreshToken: true, scopes: [...] })
[App]  GoogleSignin.signIn()                      // native consent, on-device
[App]  receives  serverAuthCode                   // a one-time authorization code
        │
        │  POST /api/v1/auth/google/exchange  { server_auth_code }   (+ Bearer to link)
        ▼
[Backend]  exchanges serverAuthCode + Web client_id + client_secret
           → access_token + refresh_token
           → stores them Fernet-encrypted as a ChannelConnection
           → upserts Account, mints app session JWT
        │
        ▼
[App]  stores the session JWT in SecureStore  → signed in
```

Implementation: `mobile/src/lib/oauth.ts` (`connectGoogle`), backend
`app/services/providers/google.py` + `app/api/v1/endpoints/auth.py`.

### `serverAuthCode` vs `id_token` vs `access_token` (don't confuse them)
- **`id_token`** — a signed JWT proving *who* the user is. Identity only; can't
  call Gmail. We don't rely on it for authorization.
- **`access_token`** — short-lived (~1 hour) key to actually call Gmail. Not
  enough on its own because it expires.
- **`serverAuthCode`** — a **one-time code** the app gets from Google and forwards
  to the backend. The backend swaps it (with the client secret) for **both** an
  access token *and* a **refresh token**. This is the only path that yields a
  refresh token on mobile.

## Refresh tokens — the rules that bite you

The refresh token is what lets the backend keep sending Gmail after the 1-hour
access token expires, without asking the user to sign in again. Google's quirks:

1. **Only issued with `offlineAccess: true`** (a.k.a. `access_type=offline`).
2. **Often only issued on the *first* consent.** If a user already granted
   access, Google may return *no* refresh token on subsequent sign-ins. This
   project sets **`forceCodeForRefreshToken: true`** and calls
   `GoogleSignin.signOut()` before `signIn()` to force a fresh code. If you still
   get none, revoke the app at
   [myaccount.google.com/permissions](https://myaccount.google.com/permissions)
   and reconnect.
3. **Expires if unused (~6 months)**, or after **7 days** while the app is in
   Testing mode (see the cap above).

The backend detects an expired access token and uses the refresh token to get a
new one automatically (`services/connections.py`, `services/sender.py`). If there
is **no** refresh token and the access token has expired, the connection is
flagged `needs_reconnect` and the app shows a **Reconnect** button (see
[MOBILE_APP_GUIDE.md](./MOBILE_APP_GUIDE.md)).

## Inbound Gmail: polling, not push

The Gmail poller (`backend/app/workers/gmail_poller.py`) checks each connected
mailbox every ~45s (`gmail_poll_interval`) using the `gmail.readonly` token,
tracks a `last_seen` marker, and POSTs new messages to `/triage` with the mailbox
as the `external_ref` (so the backend knows which tenant they belong to).

> Gmail **push** via Google Pub/Sub would be lower-latency but needs a public
> HTTPS endpoint + a Pub/Sub topic; polling keeps the local/LAN setup simple. This
> is a known future upgrade.

## Env vars (backend `.env`)
```
SENTINEL_GOOGLE_CLIENT_ID=<Web client ID>
SENTINEL_GOOGLE_CLIENT_SECRET=<Web client secret>
# scopes have a sensible default in config.py
```
Mobile `.env`: `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<the same Web client ID>`.
