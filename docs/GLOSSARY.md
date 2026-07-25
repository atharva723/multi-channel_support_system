# Glossary

One-line definitions of the terms used across these docs, so a first-time reader
never gets lost mid-page.

## Core concepts

- **Account (`account_id`)** — one tenant (one business/user) of the SaaS. Every
  row of data is tagged with it; all queries are scoped to it, so tenants can
  never see each other's data. See TOKEN_LIFECYCLE_AND_SECURITY.md.
- **Multi-tenant** — one running backend serves many isolated accounts.
- **Ticket** — a normalized support message after triage, with its criticality,
  urgency, AI draft reply, and status.
- **Escalation** — a critical ticket routed to a human agent on the mobile Desk.
- **Human-in-the-loop** — the AI drafts; a human approves/edits before it sends
  (for critical items).

## Scoring

- **Criticality `P(C=1|M)`** — the probability (0–1) that message `M` is Critical,
  computed from the LLM's token log-probabilities. Threshold 0.8 → escalate.
- **Urgency `U(t) = S0·e^(λ·t)`** — how pressing a ticket is, growing
  exponentially with wait time `t`; `λ` is per-channel. Re-computed on read so
  older unattended tickets rise. See LLM_TRIAGE_AND_SCORING.md.
- **Log-probabilities (logprobs)** — the model's confidence per candidate token;
  used to derive a calibrated probability instead of a yes/no.
- **Softmax** — turns two logits (Critical vs Informational) into a probability.

## RAG / knowledge base

- **RAG (Retrieval-Augmented Generation)** — retrieve relevant passages from the
  business's own data and make the LLM answer only from them.
- **Embedding** — a numeric vector representing a piece of text's meaning
  (`nomic-embed-text`, 768-dim here). Similar meanings → nearby vectors.
- **Chunk** — a ~700-character slice of a document that gets embedded and stored.
- **Cosine similarity** — how aligned two vectors are (−1…1); used to rank chunks
  against a question. Below `kb_min_score` (0.6) → treated as out of scope.
- **Crawl** — discovering/fetching the pages of a website (sitemap + links).
- **Scrape** — extracting the clean main text from a fetched page (`trafilatura`).
- **Out-of-scope defer** — when no chunk is relevant, the AI politely says a human
  will follow up instead of guessing.
- **Upsert** — insert-or-update; re-adding a source by the same key updates it in
  place instead of duplicating.

## Auth & security

- **OAuth 2.0** — the "sign in with Google/Discord" delegated-authorization
  standard.
- **PKCE (Proof Key for Code Exchange)** — protects the OAuth code on the device
  by proving possession of a secret verifier; used for Discord here.
- **`serverAuthCode`** — a one-time Google code the app sends to the backend, which
  swaps it (with the client secret) for access + refresh tokens.
- **Access token** — short-lived (~1h) key to call a provider API.
- **Refresh token** — long-lived credential to mint new access tokens without
  re-login. Google's issuance rules are strict — see GOOGLE_OAUTH_AND_GMAIL_API.md.
- **JWT (JSON Web Token)** — the app's own signed session token carrying
  `account_id`; the phone sends it as `Authorization: Bearer`.
- **Fernet** — symmetric encryption (AES-128-CBC + HMAC) used to store provider
  tokens encrypted at rest.
- **API key (`X-API-Key`)** — a shared secret guarding `/triage` and `/exchange`
  from arbitrary LAN callers.
- **Bot token (Discord)** — a permanent, non-expiring credential for a bot user;
  distinct from the OAuth client id/secret.
- **Gateway Intents (Discord)** — permissions a bot declares to receive certain
  events (e.g. Message Content) over the realtime gateway.
- **Consent screen / Testing mode (Google)** — the OAuth authorization UI; in
  Testing it caps at 100 users and 7-day refresh tokens until verified.

## Realtime & delivery

- **SSE (Server-Sent Events)** — a one-way stream from server to client over HTTP;
  powers in-app realtime updates while the app is open.
- **Push notification** — an OS-level alert delivered even when the app is closed,
  via Expo Push → FCM.
- **FCM (Firebase Cloud Messaging)** — Google's service that actually delivers
  notifications to Android devices.
- **Expo Push Service** — a relay that gives a simple API and hands off to FCM/APNs.
- **`google-services.json`** — public Firebase config baked into the app build.
- **Service-account key** — the secret that authorizes Expo to send via FCM.

## Platform / tooling

- **Ollama** — runs LLMs locally over HTTP; no cloud, no keys.
- **EAS (Expo Application Services)** — Expo's cloud build service; produces the
  installable APK.
- **Dev build / dev client** — a custom app binary (vs. Expo Go) that includes
  native modules and owns the `sentinel://` scheme; JS still hot-reloads via Metro.
- **Metro** — React Native's JS bundler/dev server; must run in **watch mode** to
  hot-reload.
- **Zustand** — minimal client-state store (auth, prefs, toasts).
- **TanStack Query** — server-state cache (tickets, connections, KB).
- **n8n** — a visual automation tool; here, only an optional KB-refresh scheduler.
- **`external_ref`** — the routing key (guild id / mailbox) that lets an inbound
  message resolve to the right tenant when the caller isn't authenticated.
