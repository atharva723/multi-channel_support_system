# Developer's Guide — Omnichannel AI Support Sentinel

> **Start here.** This is the hub doc: a quick overview, the folder map, how to run
> everything locally, and a table of contents linking every other doc.

## What this project is (in 4 sentences)

Sentinel is a **multi-tenant AI customer-support platform**. It ingests support
messages from **Discord** and **Gmail**, uses a **local LLM** (Ollama / llama3.2)
to score how *critical* each message is and to draft a reply, and **grounds those
replies in each business's own uploaded knowledge base** (RAG). Critical messages
are **escalated in real time** to an **Expo mobile app** (over SSE + push
notification) where a human agent approves/edits the AI draft; the reply is then
sent back out through the original channel. Non-critical messages are answered
automatically.

## The two halves

| Part | Tech | Role |
| --- | --- | --- |
| **Backend** (`backend/`) | FastAPI, async SQLAlchemy + SQLite, Ollama, httpx | The brain + integration hub. Owns tenancy, auth, encrypted tokens, LLM triage, RAG, SSE, push, and all channel I/O. |
| **Mobile** (`mobile/`) | Expo (React Native, TypeScript), Zustand, TanStack Query | The human-in-the-loop dashboard. Connects channels via OAuth, receives escalations, approves replies, manages the knowledge base. |
| **Automation** (`automation/n8n/`) | n8n | Optional. A scheduler that keeps website KB sources fresh. Not on the critical path. |

## Folder layout

```
multi-channel-support/
├── backend/
│   └── app/
│       ├── main.py               # FastAPI app factory + lifespan
│       ├── core/                 # config.py (SENTINEL_ env vars), database.py
│       ├── models/               # SQLAlchemy models (account, support, push, kb)
│       ├── schemas/              # Pydantic request/response contracts
│       ├── api/v1/endpoints/     # route handlers (auth, triage, tickets, stream, kb, notifications)
│       ├── services/             # llm_router, sender, connections, kb, rag, embeddings,
│       │                         #   web_scraper, documents, push, urgency, events, crypto, auth
│       └── workers/              # discord_bot.py (gateway listener), gmail_poller.py
├── mobile/
│   ├── app/                      # expo-router screens ((auth), (app), ticket, kb, _layout)
│   ├── src/
│   │   ├── api/client.ts         # typed API client
│   │   ├── hooks/                # Zustand stores + TanStack Query hooks
│   │   ├── components/           # UI components
│   │   ├── lib/                  # oauth, notifications, haptics, channels, time, config
│   │   └── theme/                # design tokens
│   ├── app.json                  # Expo config (plugins, package, google-services)
│   └── google-services.json      # Firebase config (public identifiers)
├── automation/n8n/               # KB website-resync scheduler
├── scripts/                      # demo-start-lan.ps1, demo-stop.ps1
└── docs/                         # you are here
```

## Local setup (end to end)

### Prerequisites
- **Python 3.11+**, **Node.js 18+**, **PowerShell** (Windows).
- **Ollama** installed and running, with two models pulled:
  ```powershell
  ollama pull llama3.2          # generation + criticality classification
  ollama pull nomic-embed-text  # knowledge-base embeddings
  ```
- An **Android phone** on the same Wi-Fi (the app is a dev build, not Expo Go).

### 1. Backend
```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env     # then fill in secrets (see BACKEND_GUIDE.md)
uvicorn app.main:app --reload
```
Health check: http://127.0.0.1:8000/health · API docs: http://127.0.0.1:8000/docs

### 2. Mobile
The app needs a **custom dev build** (native Google Sign-In + notifications +
document picker). Use the existing EAS build APK, or build one:
```powershell
cd mobile
npm install
npx eas build --profile development --platform android
```
Fill `mobile/.env` (`EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_API_KEY`,
`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`, `EXPO_PUBLIC_DISCORD_CLIENT_ID`).

### 3. Run everything at once (recommended)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-start-lan.ps1
```
This launches the backend, Discord bot, Gmail poller, and Metro (all detached),
and **auto-syncs your machine's LAN IP** into both `.env` files so the phone can
reach the backend. Stop everything with `.\scripts\demo-stop.ps1`.

> **Why LAN IP?** The phone talks to your machine over Wi-Fi, and the backend's
> workers POST to themselves using that address. It changes on reboot — the
> launcher re-detects and updates it. See TROUBLESHOOTING.md.

## Documentation map

**Concepts & architecture**
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system data-flow diagrams (multi-tenant).
- [Omnichannel App Guide.md](./Omnichannel%20App%20Guide.md) — plain-language "what is this".
- [GLOSSARY.md](./GLOSSARY.md) — one-line definitions (PKCE, Fernet, SSE, JWT, RAG…).

**Setup & integrations (the "why it works this way" facts)**
- [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md) — GCP consent screen, Web vs Android client IDs, Gmail scopes, refresh tokens, testing cap.
- [DISCORD_INTEGRATION.md](./DISCORD_INTEGRATION.md) — bot token vs OAuth client, gateway intents, PKCE redirect.
- [PUSH_NOTIFICATIONS_FCM.md](./PUSH_NOTIFICATIONS_FCM.md) — Firebase/FCM + Expo push, tap-through.
- [TOKEN_LIFECYCLE_AND_SECURITY.md](./TOKEN_LIFECYCLE_AND_SECURITY.md) — the three token types, Fernet encryption, tenant isolation.

**Component guides**
- [BACKEND_GUIDE.md](./BACKEND_GUIDE.md) — FastAPI structure, config, async DB, SSE.
- [MOBILE_APP_GUIDE.md](./MOBILE_APP_GUIDE.md) — dev build, Zustand + TanStack Query, SSE client.
- [LLM_TRIAGE_AND_SCORING.md](./LLM_TRIAGE_AND_SCORING.md) — criticality `P(C=1|M)` + urgency `U(t)`.
- [KNOWLEDGE_BASE_RAG.md](./KNOWLEDGE_BASE_RAG.md) — embeddings, retrieval, upload/website ingestion, grounding.

**Reference & operations**
- [API_REFERENCE.md](./API_REFERENCE.md) — every endpoint, auth, payloads.
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — common issues and fixes.
- [../automation/n8n/README.md](../automation/n8n/README.md) — the KB resync scheduler.

**For non-developers**
- [NON_TECHNICAL_SETUP_GUIDE.md](./NON_TECHNICAL_SETUP_GUIDE.md) — run the whole thing with zero coding background.

## The big picture in one diagram

```
 Discord / Gmail  ──►  Backend workers  ──►  POST /triage
                                               │
                            ┌──────────────────┤
                            │  LLM criticality P(C=1|M)
                            │  RAG: retrieve KB, ground draft
                            │  urgency U(t)=S0·e^(λt)
                            ▼
                 critical? ──yes──►  SSE + push ──►  Mobile Desk ──►  agent approves
                     │                                                   │
                     no                                                  ▼
                     ▼                                        reply sent via account's
              auto-reply sent                                 own encrypted tokens
```
