# API Reference

> Every backend endpoint: path, method, auth, and payload shape. Base prefix:
> `/api/v1`. Interactive docs (Swagger) are always live at
> `http://<host>:8000/docs`; this page is the annotated companion. See
> [TOKEN_LIFECYCLE_AND_SECURITY.md](./TOKEN_LIFECYCLE_AND_SECURITY.md) for the auth
> types.

## Auth legend

| Symbol | Requirement |
| --- | --- |
| 🔑 **JWT** | `Authorization: Bearer <session JWT>` — scopes to a tenant. |
| 🗝️ **API key** | `X-API-Key: <SENTINEL_API_KEY>` (when configured). |
| 🌐 **None** | Public. |

---

## System

### `GET /health` 🌐
Liveness probe. → `{ "status": "ok", "service": "...", "version": "..." }`

---

## Auth & connections

### `POST /api/v1/auth/{provider}/exchange` 🗝️
Exchange an OAuth authorization code for a session (the app-owned "Option B"
flow). `provider` ∈ `discord` | `google`.
- **Discord (PKCE):** `{ code, code_verifier, redirect_uri }`
- **Google (native):** `{ server_auth_code }`
- Optional `Authorization: Bearer` to **link** the new channel to an existing
  account instead of creating a new one.
- → `SessionOut`: `{ access_token, token_type, account, connected_provider, is_new_account }`

### `GET /api/v1/auth/{provider}/login` · `GET /api/v1/auth/{provider}/callback` 🌐
Legacy server-redirect OAuth (web/manual testing). The mobile app uses `/exchange`
instead; these remain for completeness.

### `GET /api/v1/auth/providers` 🌐
List available providers. → `{ "providers": [...] }`

### `GET /api/v1/me` 🔑
Current account + its connections. → `{ account, connections: [ConnectionOut] }`

### `GET /api/v1/connections` 🔑
List the account's channel connections. `ConnectionOut` includes
`provider`, `email`/`display_name`, `external_ref`, `token_expires_at`,
`has_refresh`, and computed **`needs_reconnect`**.

### `DELETE /api/v1/connections/{connection_id}` 🔑
Disconnect a channel.

### `GET /api/v1/connections/discord/guilds` 🔑
List the connected Discord user's servers + which one is linked.
→ `{ guilds: [{ id, name }], linked_guild }`

### `POST /api/v1/connections/discord/link-guild` 🔑
Choose which Discord server Sentinel watches. Body `{ guild_id }` → `ConnectionOut`.

---

## Triage (ingestion)

### `POST /api/v1/support/triage` 🗝️ (or 🔑)
The ingestion point every inbound message hits (called by the Discord bot / Gmail
poller / n8n). Resolves the tenant by JWT **or** by `external_ref`.

Body (`SupportIngestPayload`):
```json
{
  "channel": "discord | email",
  "channel_id": "string",
  "message_id": "string",
  "author_name": "string",
  "author_contact": "string | null",
  "content": "string",
  "timestamp": "ISO-8601 (optional)",
  "external_ref": "guild id / mailbox (resolves tenant when unauthenticated)"
}
```
→ `TriageResult`: `{ decision: ESCALATED|AUTO_REPLY, is_critical, criticality_score,
urgency_score, threshold, ticket }`. Idempotent on `(account, channel, message_id)`.
`502` if the LLM is unreachable.

---

## Tickets

### `GET /api/v1/support/tickets` 🔑
List tickets ranked by current (aged) urgency. Optional `?status=` filter
(`PENDING` | `APPROVED` | `MODIFIED` | `DISMISSED` | `AUTO_REPLIED`).
→ `[EscalationTicket]` (`created_at` serialized as UTC with offset).

### `GET /api/v1/support/tickets/{ticket_id}` 🔑
Fetch one ticket. `404` if not found / not owned.

### `PATCH /api/v1/support/tickets/{ticket_id}` 🔑
Agent action. Body `{ status: APPROVED|MODIFIED|DISMISSED, ai_draft_reply?: string }`.
On `APPROVED`/`MODIFIED` the backend **sends the reply before committing** through
the account's own provider tokens; `502` if the send fails (nothing is marked
sent). Publishes a `ticket_update` SSE event.

---

## Realtime

### `GET /api/v1/support/stream?token=<JWT>` 🔑(query)
Server-Sent Events for the current account. Token is a query param because
`EventSource` can't set headers. Event types: **`escalation`**, **`ticket_update`**
(each carries the full ticket JSON). Keepalives ~15s.

---

## Notifications (push)

### `POST /api/v1/notifications/register` 🔑
Register this device's Expo push token. Body `{ token, platform? }`. → `204`.

### `POST /api/v1/notifications/unregister` 🔑
Remove a device token (on sign-out). Body `{ token }`. → `204`.

---

## Knowledge base (RAG)

See [KNOWLEDGE_BASE_RAG.md](./KNOWLEDGE_BASE_RAG.md) for the design. `KbDocumentOut`
= `{ id, title, content_type, source, source_ref, status, chunk_count, chunk_total,
error, created_at }`.

### `POST /api/v1/kb/documents` 🔑
Upload a document (**multipart**, field `file`; PDF/DOCX/TXT/MD, ≤10 MB).
**Appends** a new document; embeds in the background. → `201 KbDocumentOut`
(`processing`).

### `POST /api/v1/kb/documents/{id}/replace` 🔑
**Overwrite** an uploaded document in place (multipart `file`). Same id, old chunks
cleared, re-embedded. → `KbDocumentOut`. `404` if not an owned upload.

### `GET /api/v1/kb/documents` 🔑
List the account's KB documents (newest first). → `[KbDocumentOut]`.

### `DELETE /api/v1/kb/documents/{document_id}` 🔑
Delete a document + its chunks. → `204`.

### `POST /api/v1/kb/sources` 🔑
Add a **website** source. Body `{ url }`. Backend crawls + scrapes + embeds in the
background. → `201 KbDocumentOut`. `400` on an invalid/unreachable URL.

### `POST /api/v1/kb/sources/{document_id}/resync` 🔑
Re-crawl one website source (replaces its chunks in place). → `KbDocumentOut`.

### `POST /api/v1/kb/sources/resync-all` 🔑
Re-crawl **all** the account's website sources (used by the n8n scheduler).
→ `{ "synced": <count> }`.

### `POST /api/v1/kb/ingest` 🔑
Ingest **raw text** directly (advanced / custom n8n flows). Body
`{ title, text, source?, source_ref? }`; upserts by `source_ref`.
→ `201 KbDocumentOut`.

---

## Status codes used
`200` OK · `201` created (async job started) · `204` no content ·
`400` bad input (parse/URL) · `401` bad/missing auth · `404` not found/owned ·
`413` file too large · `502` upstream failure (LLM / channel send).
