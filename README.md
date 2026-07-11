# Omnichannel AI Support Sentinel

A distributed, real-time support-triage pipeline. It ingests support requests from
**Slack, Discord, and IMAP (email)** via **n8n**, classifies criticality with a local
LLM, computes dynamic SLA urgency, persists escalations, and surfaces a human-in-the-loop
**Expo** mobile dashboard.

## Architecture

```
[ Discord ] [ Slack ] [ IMAP ]           Community users
      \        |        /
       \       |       /   webhooks / poller
        v      v      v
        [  n8n Triage Router  ]   normalizes -> SupportIngestPayload
                 |
                 |  POST /api/v1/support/triage
                 v
        [   FastAPI Backend   ]
          - LLM Router (Ollama): P(C=1|M)
          - Urgency scoring:     U(t) = S0 * e^(lambda_c * t)
          - Persists Ticket -> SQLite
                 |
        +--------+------------------------------+
        | P(C|M) >= 0.8                          | P(C|M) < 0.8
        v                                        v
  [ SSE gateway -> Expo dashboard ]      [ Auto-reply draft -> n8n ]
  (haptics, Zustand, TanStack Query)     (Discord/Slack POST or SMTP)
```

FastAPI is the only holder of platform secrets; the mobile client holds just an agent JWT.

## Monorepo layout

| Path           | Purpose                                             |
| -------------- | --------------------------------------------------- |
| `backend/`     | Async FastAPI service (SQLite + SQLAlchemy 2.x)     |
| `mobile/`      | Expo (React Native, TypeScript) dashboard client    |
| `automation/`  | n8n workflow exports and setup notes                |
| `docs/`        | Specification and companion guides                  |

## Backend — getting started

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env   # then edit values
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs (Swagger UI) or hit http://127.0.0.1:8000/health.

Configuration is centralized in `app/core/config.py` (env vars use the `SENTINEL_` prefix).

## Mobile — getting started

```powershell
cd mobile
npm install
npx expo start
```

## Tech stack

- **Backend:** FastAPI, SQLAlchemy 2.x (async), aiosqlite, Pydantic v2, sse-starlette, httpx
- **LLM:** Ollama (local), accessed over HTTP
- **Mobile:** Expo, TypeScript, Zustand, TanStack Query, FlashList, @gorhom/bottom-sheet, expo-haptics
- **Automation:** n8n

## Status

Phase 0 (foundation) complete: monorepo scaffold, async DB layer, `Ticket` model,
Pydantic contracts, and a booting FastAPI app with a `/health` probe. Feature endpoints
(triage, tickets, SSE), the LLM router, urgency service, n8n workflow, and mobile wiring
are the subsequent phases.
