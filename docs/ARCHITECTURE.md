# Architecture & Data Flow (Multi-Tenant, updated)

This supersedes the single-tenant DFD in the original specification. The system
is now a **multi-tenant SaaS**: many independent users (accounts), each connecting
their own channels via OAuth, fully isolated by `account_id`.

## Actors & components

| Component | Role |
| --- | --- |
| **Expo mobile app** | The dashboard. Connects channels (OAuth), holds the app **JWT**, lists tickets, approves/edits replies, listens to SSE. |
| **FastAPI backend** | The brain + integration hub. Owns tenancy, auth, encrypted token store, LLM triage, urgency, SSE, and **per-account sending**. |
| **Ollama (llama3.2)** | Local LLM: criticality `P(C=1|M)` + draft replies. |
| **SQLite DB** | `accounts`, `channel_connections` (encrypted tokens), `support_tickets` (all `account_id`-scoped). |
| **Providers** | Google (Gmail) and Discord — identity + send. (Slack was dropped.) |
| **n8n** | **Optional now.** A fallback reply sender, or an inbound forwarder that must pass `external_ref`. No longer holds per-tenant secrets. |

## Flow A — Onboarding / Sign-in ("Option B": app-owned OAuth, no tunnel)

The mobile app performs OAuth **itself** and posts the resulting authorization
code to the backend, which does the secure token exchange. There is **no public
backend callback URL / tunnel** — redirect identities are fixed and registered once.

```
[Mobile] --tap "Connect Gmail/Discord"-->  runs OAuth on-device
   • Discord: expo-auth-session PKCE -> redirect sentinel://oauthredirect
   • Google : native @react-native-google-signin -> serverAuthCode
                                               |
                                               |  POST /auth/{provider}/exchange
                                               |  (code / serverAuthCode [+ Bearer to link])
                                               v
                       [FastAPI /auth/{provider}/exchange]
                           | exchange code -> tokens
                           | fetch identity (email / user id / guild id)
                           | upsert Account (first connect = sign-up)
                           | store ENCRYPTED tokens as a ChannelConnection
                           | mint app JWT (carries account_id)
                           v
                   returns { access_token: <JWT>, account }
                           |
                           v
                   [Mobile stores JWT in SecureStore]  --> signed in
```

Connecting a second provider while signed in **links** it to the same account
(the mobile client sends its existing `Bearer` token on the exchange call).

## Flow B — Runtime: message in → escalation → approve → send out

```
                         (customer sends a message)
   [Discord]              [Gmail]
     (gateway bot)        (poller ~45s)   INBOUND INGESTION  (LIVE)
     discord_bot.py       gmail_poller.py resolves account via external_ref
        |                    |
        v                    v
        [ Inbound listener -> POST /api/v1/support/triage ]
                    |  POST /api/v1/support/triage
                    |  (Bearer JWT  OR  external_ref = mailbox/guild/team)
                    v
            +-----------------------------+
            |   FastAPI  /support/triage  |
            |  0 resolve account (tenant) |
            |  1 idempotency (acct+chan)  |
            |  2 LLM: P(C=1|M)  ----------+---> [Ollama llama3.2]
            |  3 LLM: draft reply         |
            |  4 urgency U(t)=S0*e^(λc t) |
            |  5 persist Ticket(account)  |
            +--------------+--------------+
                           |
            P(C|M) >= 0.8  |  P(C|M) < 0.8
              (ESCALATED)  |  (AUTO_REPLIED)
                    |      |        |
                    v      |        v
   [SSE /support/stream]   |   reply auto-sent via the account's
   filtered by account_id  |   own encrypted provider tokens
                    |      |
                    v      |
        [Mobile Escalation Desk]  <-- only THIS account's tickets
           haptics + FlashList + Zustand + TanStack Query
                    |
           agent approves / edits reply
                    |  PATCH /support/tickets/{id}  (Bearer JWT)
                    v
            +-----------------------------+
            | FastAPI: update status      |
            | send BEFORE commit:         |
            |  look up THIS account's     |
            |  ChannelConnection for the  |
            |  ticket's channel           |
            |  -> decrypt tokens          |
            |  -> provider.send_message() ----> [Gmail / Discord]
            | (fallback: n8n webhook)     |
            +--------------+--------------+
                           |  publish ticket_update (account-scoped)
                           v
                 [All of this account's dashboards update live]
```

## What changed vs the original (single-tenant) DFD

1. **New onboarding flow (Flow A)** — OAuth connect is both login and send-auth.
2. **Tenant isolation** — every ticket/connection carries `account_id`; all
   queries, the SSE stream, and idempotency are scoped to the caller's account.
3. **Sending moved into the backend** — replies go out through *the account's own*
   provider tokens (`services/sender.py`), not a shared n8n credential.
4. **Secrets moved into the backend** — provider tokens are encrypted at rest
   (Fernet); n8n no longer stores per-tenant credentials.
5. **n8n is optional** — a fallback sender, or an inbound forwarder that must
   include `external_ref`. It is no longer on the critical path.
6. **Inbound ingestion is LIVE** — a Discord gateway bot (`discord_bot.py`) and a
   Gmail poller (`gmail_poller.py`) call `/triage` with `external_ref` to resolve
   the tenant. (Slack was dropped; Gmail push/Pub-Sub is a future upgrade over polling.)
7. **Mobile OAuth is "Option B"** — the app performs OAuth itself (Discord PKCE /
   native Google) and posts the code to `/auth/{provider}/exchange`; no tunnel.
8. **Push notifications on escalation** — on a critical ticket the backend, in
   addition to the SSE event, sends an Expo push (`services/push.py`) to that
   account's registered devices so the agent is alerted even when the app is
   closed. Tapping it deep-links to `/ticket/{id}`. Device tokens are stored in
   `push_tokens` and registered via `POST /notifications/register`. Android
   delivery goes through Firebase FCM V1 (see README).
9. **RAG knowledge base grounds replies** — each account has a private KB
   (`kb_documents` + `kb_chunks`, account-scoped). At draft time `triage.py`
   embeds the message (`nomic-embed-text` via Ollama), cosine-matches the
   account's chunks (`services/kb.py`), and grounds the reply in the top
   passages. Relevant context → grounded reply; a KB exists but nothing matches →
   polite out-of-scope defer; no KB → general reply. KB input: mobile **file
   upload** (`POST /kb/documents`, parsed by pypdf/python-docx) **and** a
   **website source** (`POST /kb/sources`) that the backend crawls
   (`services/web_scraper.py`: sitemap + same-domain links, policy/FAQ first) and
   scrapes to clean main text with `trafilatura`. Websites re-crawl on demand
   (`/kb/sources/{id}/resync`) or on a schedule via the n8n resync workflow
   (`/kb/sources/resync-all`). All inputs share one chunk→embed→store pipeline.

## Token glossary (don't confuse these)

- **Provider OAuth token** — key to act on a channel (send Gmail / post Discord).
  Stored **encrypted** per `ChannelConnection`. Used only for sending.
- **App JWT (session)** — the app's own membership card carrying `account_id`.
  Held by the mobile client, sent as `Authorization: Bearer` on every request,
  used purely to identify + scope the tenant.
