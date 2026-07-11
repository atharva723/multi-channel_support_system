# n8n Automation Layer

n8n is the operational router. It listens for messages on Discord, Slack, and IMAP,
normalizes them, POSTs them to the FastAPI backend for triage, and owns **all**
outbound platform sends. It runs **project-local** (its SQLite DB + encryption key
live in this folder's `.n8n`), installed via npm just like a standalone project.

Two workflows live in `workflows/`:

- **`triage-router.workflow.json`** — ingest → normalize → `/triage` → auto-reply
  for non-critical tickets.
- **`reply-dispatcher.workflow.json`** — a webhook the **backend** calls when an
  agent approves/edits a reply on the mobile app, so critical replies actually get
  sent through the right channel.

## Two workflows, one loop

### 1. Triage Router (inbound)

```
[Discord Webhook] --> [Normalize Discord] --\
[Slack Webhook]   --> [Normalize Slack]   ---+--> [Post to FastAPI /triage]
[IMAP Trigger]    --> [Normalize Email]   --/            |
                                                          v
                                                   {Is Critical?}
                                                    /          \
                                                (Yes)          (No)
                                                  |              |
                                                  v              v
                                   [Escalated — SSE handled   [Route by Channel]
                                    by the backend, no-op]      /     |      \
                                                          Discord   Slack   SMTP
                                                          reply     reply   reply
```

When a ticket is **critical**, the backend has *already* pushed the escalation to
the mobile dashboard over SSE during `/triage`, so the critical branch here is a
no-op. n8n only auto-sends on the **non-critical** branch.

### 2. Reply Dispatcher (outbound / human-in-the-loop)

This is the answer to "how does an approved reply actually get sent?" The mobile
app never touches Discord/Slack/SMTP — it only talks to the backend. On approve,
the backend hands the reply to n8n:

```
Agent taps Approve/Send (mobile)
   -> PATCH /api/v1/support/tickets/{id}   (status=APPROVED|MODIFIED, reply text)
   -> backend POSTs to  http://localhost:5678/webhook/send-reply
   -> [Send-Reply Webhook] -> [Normalize] -> [Route by Channel]
                                               /     |      \
                                          Discord  Slack   SMTP  (send)
```

Payload the backend sends to `/webhook/send-reply`:

```json
{
  "ticket_id": 1,
  "channel": "discord",
  "channel_id": "...",
  "author_name": "...",
  "author_contact": "...",
  "reply_text": "the approved/edited reply"
}
```

Enable it by setting `SENTINEL_N8N_REPLY_WEBHOOK_URL=http://localhost:5678/webhook/send-reply`
on the backend. If unset, the PATCH still updates status but sends nothing (fine
for local dev before n8n is wired up).

## Project-local setup (matches the n8n-Maps pattern)

n8n is installed **in this folder** and stores its data in `./.n8n` (via
`N8N_USER_FOLDER` in `.env`), so the project is self-contained. `npm` scripts wrap
the n8n CLI with `dotenv`:

```powershell
cd automation\n8n
copy .env.example .env        # already seeded; adjust port/timezone if needed
npm install                    # installs project-local n8n + dotenv-cli

npm run import                 # imports workflows/*.json into ./.n8n DB
npm start                      # launches the editor at http://localhost:5678
npm run export                 # export live workflows back to workflows/ (after UI edits)
```

> The data folder ends up at `automation\n8n\.n8n\.n8n\database.sqlite` (n8n
> appends its own `.n8n` under `N8N_USER_FOLDER`) — the same nesting as n8n-Maps.

### Typical first-time flow

1. `npm start` → open http://localhost:5678 → create the owner account.
2. Create Credentials (below) and attach them to the nodes in both workflows.
3. Toggle each workflow **Active**.
4. `npm run export` to snapshot your wired-up workflows back into `workflows/`.

Re-importing (`npm run import`) after editing the JSON updates the workflows by id.

### Alternative: import via the UI

n8n → **Workflows → ⋮ → Import from File** → select a file from `workflows/`.
Handy while iterating on a single workflow.

## Credentials to create in the UI (kept in n8n, never in the mobile client)

Create these under **Credentials**, then open each reply/trigger node and select
the matching credential (the JSON has `REPLACE_*_CREDENTIAL_ID` placeholders):

- **Discord Bot API** - bot token (instant, non-expiring).
- **Slack API** - app/bot token (workspace sandbox).
- **IMAP** - host + user + app password (bypasses OAuth audits).
- **SMTP** - host + user + app password (for email auto-replies).

## Connecting to the backend

The `Post to FastAPI Triage` node targets `http://localhost:8000/api/v1/support/triage`.

- If n8n and FastAPI run on different hosts/containers, change that URL.
- If you set `SENTINEL_API_KEY` on the backend, set a `SENTINEL_API_KEY`
  environment variable for the n8n process too - the node sends it as the
  `X-API-Key` header. If the backend has no API key configured, the header is
  simply ignored.

## Webhook endpoints (for platform configuration)

Once active, n8n exposes:

- Discord -> `POST http://<n8n-host>:5678/webhook/discord-ingest`
- Slack   -> `POST http://<n8n-host>:5678/webhook/slack-ingest`

Point your Discord interaction / Slack Events subscription URLs at these. The IMAP
trigger polls the mailbox directly using the IMAP credential.

## Normalization contract

Each Code node emits exactly this shape (validated by the backend's
`SupportIngestPayload`); `channel` must be one of `slack`, `discord`, `email`:

```json
{
  "channel": "discord",
  "channel_id": "...",
  "message_id": "...",
  "author_name": "...",
  "author_contact": "...",
  "content": "..."
}
```
