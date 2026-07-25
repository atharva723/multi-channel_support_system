# Backend Guide

> How the FastAPI backend is structured and the patterns it uses. Reference for
> endpoints is in [API_REFERENCE.md](./API_REFERENCE.md); triage/scoring detail is
> in [LLM_TRIAGE_AND_SCORING.md](./LLM_TRIAGE_AND_SCORING.md).

## Stack

FastAPI · async SQLAlchemy 2.x + `aiosqlite` (SQLite) · Pydantic v2 &
`pydantic-settings` · `sse-starlette` · `httpx` · `cryptography` (Fernet) ·
`discord.py` · `pypdf` + `python-docx` + `trafilatura` + `numpy` (knowledge base).
LLM + embeddings run on **Ollama** over HTTP.

## App structure

```
app/
├── main.py                 # create_app() factory + lifespan (init_db, close clients)
├── core/
│   ├── config.py           # Settings (pydantic-settings), SENTINEL_ env prefix
│   └── database.py         # async engine, AsyncSessionLocal, Base, init_db
├── models/                 # SQLAlchemy ORM (account, support, push, kb)
├── schemas/                # Pydantic contracts (triage, account, kb)
├── api/
│   ├── deps.py             # shared dependencies (DB, auth, api-key, broker, llm)
│   └── v1/
│       ├── router.py       # aggregates all endpoint routers
│       └── endpoints/      # auth, triage, tickets, stream, kb, notifications
├── services/               # business logic (see below)
└── workers/                # discord_bot.py, gmail_poller.py (run as separate processes)
```

### Services (the logic layer)
| Module | Responsibility |
| --- | --- |
| `llm_router.py` | Ollama calls: criticality classification + reply drafting (incl. RAG-grounded + out-of-scope prompts). |
| `embeddings.py` | Ollama `/api/embeddings` client (`nomic-embed-text`). |
| `kb.py` | Knowledge-base ingest (chunk→embed→store), retrieval (cosine), website + upload + replace flows. |
| `web_scraper.py` | Crawl + scrape websites (sitemap/link discovery, `trafilatura` extraction). |
| `documents.py` | Parse PDF/DOCX/TXT/MD → text; chunking. |
| `sender.py` | Send an approved reply through the account's own provider tokens. |
| `connections.py` | Encrypted token store; refresh/expiry handling. |
| `providers/` | Per-provider OAuth + send (`google.py`, `discord.py`, `base.py`). |
| `push.py` | Expo push send + device-token registration/pruning. |
| `urgency.py` | Urgency `U(t)=S0·e^(λt)` scoring. |
| `events.py` | In-process pub/sub broker feeding the SSE stream. |
| `crypto.py` | Fernet encrypt/decrypt for tokens at rest. |
| `auth.py` | Session JWT + OAuth state token mint/verify. |

## Configuration (`core/config.py`)

All settings are a single typed `Settings` (pydantic-settings) loaded from
environment variables with the **`SENTINEL_` prefix** and an optional `.env` file.
So `app_base_url` ← `SENTINEL_APP_BASE_URL`, `ollama_model` ← `SENTINEL_OLLAMA_MODEL`,
etc. One source of truth; import `from app.core.config import settings`.

Notable knobs: `criticality_threshold` (0.8), `auto_reply_enabled`, urgency
`lambda_*` per channel, `kb_chunk_size`/`kb_top_k`/`kb_min_score`,
`kb_web_max_pages`, `gmail_poll_interval`. See the file's inline comments.

## Async database layer (`core/database.py`)

- `create_async_engine("sqlite+aiosqlite:///./sentinel.db")` + an
  `async_sessionmaker` (`AsyncSessionLocal`, `expire_on_commit=False`).
- `get_session()` is the FastAPI dependency yielding a scoped `AsyncSession`;
  `get_db()` in `deps.py` re-exports it as `DBSession`.
- `init_db()` runs `Base.metadata.create_all` on startup (wired into the app
  lifespan). It imports `app.models` for the side effect of registering every
  table.

> **Schema changes:** `create_all` only *creates missing* tables — it does **not**
> alter existing ones. When a column is added to an existing table (as with the
> KB `chunk_total`), apply a one-off `ALTER TABLE ... ADD COLUMN` on the existing
> `sentinel.db` (fresh installs pick it up automatically). There's no Alembic yet.

## Request lifecycle & dependencies (`api/deps.py`)

Readable route signatures use these aliases:
- `DBSession` → async session.
- `CurrentAccount` → `require_account`: decodes the `Bearer` JWT, loads the
  `Account`, and scopes the request to that tenant. Rejects missing/invalid tokens
  with 401.
- `ApiKeyGuard` → `require_api_key`: enforces `X-API-Key` when `SENTINEL_API_KEY`
  is set (used by `/triage` and `/exchange`).
- `Broker` → the SSE event broker singleton.
- `Router` → the `LLMRouter` singleton.

## Real-time: SSE (`endpoints/stream.py` + `services/events.py`)

- `EventBroker` is a lightweight in-process pub/sub over `asyncio.Queue`. Each SSE
  connection `subscribe()`s to get its own queue; producers (triage on escalation,
  tickets on status change) `publish()` an `Event` that fans out to all queues.
- Events are **account-scoped**: each `Event` carries an `account_id`, and the
  stream only forwards events matching the connected tenant.
- `sse-starlette`'s `EventSourceResponse` streams them; keepalives every ~15s.
- The token is passed as a `?token=` query param (EventSource can't send
  headers). Event types: `escalation`, `ticket_update`.
- **Scope note:** in-process broker = single worker. Scaling to multiple workers
  would swap this for Redis pub/sub behind the same interface.

## The triage pipeline (`endpoints/triage.py`)

`POST /support/triage` is the ingestion point every inbound message hits:

0. Resolve account (from JWT or by inbound `external_ref`).
1. Idempotency guard on `(account, channel, message_id)`.
2. LLM criticality `P(C=1|M)`.
3. RAG: retrieve KB context → draft a **grounded** reply (or out-of-scope defer).
4. Urgency `U(t)`.
5. Persist the `Ticket`.
6. Branch: **critical** → publish `escalation` (SSE) **and** send a push;
   **non-critical** → `send_reply` immediately and mark `AUTO_REPLIED`.

## Workers (separate processes)

- `workers/discord_bot.py` — a `discord.py` gateway bot; forwards messages to
  `/triage`. See [DISCORD_INTEGRATION.md](./DISCORD_INTEGRATION.md).
- `workers/gmail_poller.py` — polls connected mailboxes every ~45s; forwards new
  mail to `/triage`. See [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md).

Both are launched (detached) by `scripts/demo-start-lan.ps1` alongside the API.

## Running & docs

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```
Interactive API docs (Swagger) at `/docs`; OpenAPI JSON at `/openapi.json`.
