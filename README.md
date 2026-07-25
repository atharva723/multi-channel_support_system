# Omnichannel AI Support Sentinel

A real-time, multi-tenant support-triage platform. It ingests support requests from
**Discord and Gmail**, classifies criticality with a **local LLM**, computes dynamic
SLA urgency, escalates critical tickets to a human-in-the-loop **Expo** mobile
dashboard, and sends approved (or AI-auto) replies back through the original channel.
Replies are **grounded in each tenant's own knowledge base** (RAG) so answers
reflect the business's real info — and out-of-scope questions defer to a human.

> **Multi-tenant SaaS:** every user (account) connects their own channels via OAuth
> and only ever sees their own tickets — all data is isolated by `account_id`.

> 📚 **Full documentation:** see **[docs/](./docs/README.md)** — start with the
> **[Developer's Guide](./docs/DEVELOPERS_GUIDE.md)** (hub), or the
> **[Non-Technical Setup Guide](./docs/NON_TECHNICAL_SETUP_GUIDE.md)** to run it
> with no coding background.

## Architecture (current)

```
  Discord server                     Gmail mailbox
        │                                  │
        │  Discord gateway bot             │  Gmail poller (every ~45s)
        │  (discord_bot.py)                │  (gmail_poller.py)
        ▼                                  ▼
        └──────────────┬───────────────────┘
                       │  POST /api/v1/support/triage
                       │  (API key + external_ref = guild id / mailbox)
                       ▼
             ┌───────────────────────────┐
             │   FastAPI backend         │
             │   • resolve account       │
             │   • LLM: P(C=1|M)  ───────┼──► Ollama (llama3.2, local)
             │   • RAG: retrieve KB  ────┼──► Ollama (nomic-embed-text)
             │   • draft reply (grounded)│      + kb_chunks (SQLite)
             │   • urgency U(t)=S0·e^(λt) │
             │   • persist Ticket → SQLite│
             └───────────┬───────────────┘
                         │
          P(C|M) ≥ 0.8   │   P(C|M) < 0.8
           (ESCALATED)   │   (AUTO_REPLIED)
                 │       │        │
                 ▼       │        ▼
        SSE /support/stream       reply sent automatically
        + push (FCM)              via the channel's own tokens
        (account-scoped)
                 │
                 ▼
        Expo Escalation Desk  ── agent approves / edits ──► PATCH /tickets/{id}
        (realtime, haptics)                                     │
                                                                ▼
                                            reply sent via THIS account's
                                            encrypted Gmail / Discord tokens

  Knowledge base (per account):
    mobile upload ─┐                    app "Add website" ─┐
                   ▼                                       ▼
        POST /kb/documents        POST /kb/sources ─► backend crawls + scrapes
                   │                    (clean main content, sitemap/links)
                   ▼                                       │
             parse (pypdf/docx)                            │
                   └──────────────►  chunk → embed  ◄──────┘
                                     (nomic-embed-text)
                                        │
                                        ▼   kb_chunks (SQLite, account-scoped)
                              retrieved at draft time to ground replies
                        (n8n resync scheduler keeps website sources fresh)
```

The **FastAPI backend is the only holder of platform secrets** (provider OAuth
tokens, encrypted at rest with Fernet). The mobile client holds only a session **JWT**.

### Mobile OAuth = "Option B" (app-owned, no tunnel)

The app performs OAuth itself and posts the resulting code to the backend to
exchange for tokens — so there is **no public callback URL / tunnel** to maintain:

- **Discord:** `expo-auth-session` PKCE → fixed redirect `sentinel://oauthredirect`.
- **Google:** native `@react-native-google-signin` → `serverAuthCode` → backend exchange.

## Monorepo layout

| Path           | Purpose                                                        |
| -------------- | -------------------------------------------------------------- |
| `backend/`     | Async FastAPI service (SQLite + SQLAlchemy 2.x), workers       |
| `mobile/`      | Expo (React Native, TypeScript) dashboard client               |
| `automation/`  | n8n workflow exports (optional / legacy fallback)              |
| `docs/`        | Specification and companion guides                             |
| `scripts/`     | Local dev launchers (`demo-start-lan.ps1`, `demo-stop.ps1`)    |

## Channels

| Channel     | Inbound (message → ticket)                | Outbound (reply)                    |
| ----------- | ----------------------------------------- | ----------------------------------- |
| **Discord** | Gateway bot listener (`discord_bot.py`)   | Bot posts to the channel            |
| **Gmail**   | Poller (`gmail_poller.py`, ~45s)          | Gmail API send as the user          |
| ~~Slack~~   | Dropped — not implemented                 | —                                   |

## Backend — getting started

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env   # then edit values (see below)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs (Swagger UI) or http://127.0.0.1:8000/health.
Configuration is centralized in `app/core/config.py` (env vars use the `SENTINEL_` prefix).

Key env vars: `SENTINEL_API_KEY` (protects `/triage` + `/exchange`), a JWT secret,
a Fernet key, `SENTINEL_APP_BASE_URL` (LAN IP the workers POST to), Google/Discord
OAuth client credentials, and the Discord bot token.

## Mobile — getting started

The mobile app uses native modules (Google Sign-In), so it runs in a **custom
Expo dev build**, not Expo Go:

```powershell
cd mobile
npm install
# then use an existing EAS dev build APK, or build one:
npx eas build --profile development --platform android
```

`mobile/.env` needs `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_API_KEY`,
`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`, and `EXPO_PUBLIC_DISCORD_CLIENT_ID`.

## Local demo (everything at once)

`scripts/demo-start-lan.ps1` launches the backend, the Discord bot, the Gmail
poller, and Metro (watch mode) — all detached — and auto-syncs the LAN IP into
both `.env` files. `scripts/demo-stop.ps1` stops them.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-start-lan.ps1
```

## Tech stack

- **Backend:** FastAPI, SQLAlchemy 2.x (async), aiosqlite, Pydantic v2, sse-starlette, httpx, cryptography (Fernet), pypdf + python-docx (KB parsing), trafilatura (website scraping), numpy (retrieval)
- **LLM:** Ollama (local) — `llama3.2` (generation) + `nomic-embed-text` (embeddings)
- **Mobile:** Expo SDK 57, TypeScript, Zustand, TanStack Query, FlashList, @gorhom/bottom-sheet, expo-router, expo-haptics, expo-notifications, expo-document-picker, react-native-sse
- **Automation:** n8n — KB auto-ingestion side-car (not on the message critical path)

## Feature status

**Working end-to-end:**
- ✅ Discord + Gmail inbound → LLM triage → ticket
- ✅ LLM criticality `P(C=1|M)` + urgency `U(t)` scoring
- ✅ Escalation to the mobile Desk over SSE (account-scoped, realtime)
- ✅ Approve / edit / dismiss → reply sent back through the original channel
- ✅ Non-critical auto-reply (`AUTO_REPLIED`) via the account's own tokens
- ✅ Multi-tenant accounts with encrypted per-channel token storage
- ✅ Mobile OAuth (Option B), channel management, connection health/reconnect
- ✅ Push notifications for critical escalations (Expo Push + FCM V1) with
  tap-through deep-linking to the ticket
- ✅ **RAG knowledge base** — per-tenant docs (upload + n8n auto-ingest) ground
  replies; out-of-scope questions politely defer to a human

**Not yet implemented:**
- ⛔ Slack (dropped from scope)
- ⛔ Gmail push/Pub-Sub (inbound uses polling)

## Knowledge base (RAG)

Each account has a private knowledge base that grounds AI replies:

- **Input paths:** (a) **file upload** from the mobile app (PDF/DOCX/TXT/MD), and
  (b) **website** — the user adds a business URL in the app and the backend
  **crawls** the site (start page + sitemap + same-domain links, prioritizing
  policy/FAQ/help pages) and **scrapes** clean main content with `trafilatura`
  (drops nav/footer/ads). Both funnel through one shared chunk → embed → store
  pipeline (`services/kb.py`).
- **Embeddings:** Ollama `nomic-embed-text` (768-dim), stored per chunk in SQLite
  (`kb_documents` + `kb_chunks`, account-scoped). Prereq: `ollama pull nomic-embed-text`.
- **At draft time** (`triage.py`): the incoming message is embedded and
  cosine-matched against the account's chunks. Relevant context → the reply is
  grounded strictly in it; nothing relevant but a KB exists → **out-of-scope**,
  the AI politely says a teammate will follow up; no KB at all → general reply.
- **Freshness:** website sources can be re-crawled on demand (a "Refresh" action
  in the app / `POST /kb/sources/{id}/resync`) or on a schedule via the n8n
  `kb-website-resync` workflow (`POST /kb/sources/resync-all`). Uploads are
  one-shot; websites stay in sync.
- **Tuning** lives in `config.py` (`kb_chunk_size`, `kb_top_k`, `kb_min_score`,
  `kb_web_max_pages`, the `search_document:`/`search_query:` prefixes).
  `kb_min_score` (0.6) is calibrated for `nomic-embed-text`'s similarity range.

KB endpoints: `POST /kb/documents` (upload — appends a new doc),
`POST /kb/documents/{id}/replace` (overwrite one uploaded doc in place),
`POST /kb/sources` (add website), `POST /kb/sources/{id}/resync` +
`/kb/sources/resync-all` (refresh), `POST /kb/ingest` (raw text, for advanced
n8n flows), `GET`/`DELETE /kb/documents`.

**Add vs. overwrite:** uploading a document always **appends** it to the KB (so
you can grow it incrementally); to fix an outdated/wrong doc, use **Replace** on
that document, which re-embeds it **in place** (same entry, old chunks removed)
without touching your other documents. Website sources upsert by URL
(re-crawling updates in place). The KB is fully **per-account isolated**.

See `automation/n8n/README.md` for the resync scheduler.

## Push notifications (FCM)

The push pipeline is fully built and configured: device token registration,
`services/push.py` sending via the Expo Push API on escalation, mobile
tap-through, and Android delivery through **Firebase Cloud Messaging (FCM V1)**.

Android delivery is wired via:
1. A Firebase project (`sentinel-app-98550`) with an Android app for package `com.sentinel.app`.
2. `mobile/google-services.json` referenced by `expo.android.googleServicesFile` in `app.json` (committed — public identifiers only).
3. A Google **service-account key** uploaded to EAS (Android → FCM V1). The local
   copy lives at `mobile/credentials/fcm-service-account.json` and is **gitignored** (secret).

To reproduce on a fresh Firebase project, see the same three steps — then rebuild
the dev app (`eas build --profile development --platform android`) and reinstall.
