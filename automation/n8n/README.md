# n8n Automation Layer

> **What n8n does in this project:** exactly one thing — **keep website
> knowledge-base sources fresh on a schedule**. The FastAPI backend owns
> everything on the message critical path (inbound via its Discord gateway bot +
> Gmail poller, outbound via `services/sender.py`, and all KB crawling/embedding).
> n8n is just an optional **clock** that periodically tells the backend to
> re-crawl saved websites. If you never run n8n, the app still works fully — you
> just re-crawl manually with the "Refresh" button in the app.

n8n runs **project-local**: its SQLite DB + encryption key live in this folder's
`.n8n`, so the setup is self-contained.

## The one workflow: KB Website Resync

`workflows/kb-website-resync.workflow.json`

```
[Schedule: every 24h] -> [HTTP POST /api/v1/kb/sources/resync-all  (Bearer tenant JWT)]
                                        |
                                        v
                     backend re-crawls each saved website source, re-cleans,
                     re-embeds (nomic-embed-text) -> account's KB (upsert)
```

Websites are **added in the app** (Knowledge Base screen → "Add website"); the
backend crawls them immediately on add. This workflow only keeps them fresh over
time. All crawling, scraping, and embedding happen **in the backend** — n8n never
touches page content, it only fires the resync call.

## Setup

```powershell
cd automation\n8n
copy .env.example .env        # then fill in the values below
npm install                    # installs project-local n8n + dotenv-cli
npm run import                 # imports workflows/*.json into ./.n8n DB
npm start                      # launches the editor at http://localhost:5678
```

Configure in `automation/n8n/.env` (see `.env.example`):

- `SENTINEL_BACKEND_URL` — backend base URL (default `http://localhost:8000`).
- `SENTINEL_ACCOUNT_TOKEN` — the tenant's app **session JWT** (Bearer). The
  scheduler resyncs **as that account**, so each tenant runs their own copy with
  their own token. Grab the token from the app (it's stored after sign-in) or
  mint one server-side with `app.services.auth.create_session_token(account_id)`.

Then in the n8n UI: open the workflow, confirm the schedule interval, and toggle
it **Active**. Run `npm run export` to snapshot any UI edits back to `workflows/`.

## Notes

- **File uploads never touch n8n** — the app posts them straight to the backend
  (`POST /kb/documents`). Only website *freshness* uses this scheduler.
- The KB endpoints are protected by the **account JWT** (not the backend's
  `SENTINEL_API_KEY`), so the workflow only needs `SENTINEL_ACCOUNT_TOKEN`.

See `../../docs/KNOWLEDGE_BASE_RAG.md` for the full knowledge-base + RAG design.
