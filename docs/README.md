# Documentation Index

Modular docs for **Omnichannel AI Support Sentinel**. New here? Start with the
**[Developer's Guide](./DEVELOPERS_GUIDE.md)** (the hub) or, if you're
non-technical, the **[Non-Technical Setup Guide](./NON_TECHNICAL_SETUP_GUIDE.md)**.

## By topic

### Concepts & architecture
- **[DEVELOPERS_GUIDE.md](./DEVELOPERS_GUIDE.md)** — hub: overview, folder map, local setup, links to everything.
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system data-flow diagrams (multi-tenant).
- [Omnichannel App Guide.md](./Omnichannel%20App%20Guide.md) — plain-language "what is this".
- [GLOSSARY.md](./GLOSSARY.md) — one-line definitions of every term.

### Integrations & the "why it works this way" facts
- [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md) — GCP consent screen, Web vs Android client IDs, Gmail scopes, refresh tokens.
- [DISCORD_INTEGRATION.md](./DISCORD_INTEGRATION.md) — bot token vs OAuth client, gateway intents, PKCE redirect.
- [PUSH_NOTIFICATIONS_FCM.md](./PUSH_NOTIFICATIONS_FCM.md) — Firebase/FCM + Expo push, tap-through.
- [TOKEN_LIFECYCLE_AND_SECURITY.md](./TOKEN_LIFECYCLE_AND_SECURITY.md) — the three token types, Fernet, tenant isolation.

### Component guides
- [BACKEND_GUIDE.md](./BACKEND_GUIDE.md) — FastAPI structure, config, async DB, SSE.
- [MOBILE_APP_GUIDE.md](./MOBILE_APP_GUIDE.md) — dev build, Zustand + TanStack Query, SSE client.
- [LLM_TRIAGE_AND_SCORING.md](./LLM_TRIAGE_AND_SCORING.md) — criticality `P(C=1|M)` + urgency `U(t)`.
- [KNOWLEDGE_BASE_RAG.md](./KNOWLEDGE_BASE_RAG.md) — embeddings, retrieval, upload/website ingestion, grounding.

### Reference & operations
- [API_REFERENCE.md](./API_REFERENCE.md) — every endpoint, auth, payloads.
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — common issues and fixes.
- [../automation/n8n/README.md](../automation/n8n/README.md) — the KB resync scheduler.

### For non-developers
- [NON_TECHNICAL_SETUP_GUIDE.md](./NON_TECHNICAL_SETUP_GUIDE.md) — run the whole thing with zero coding background.

### Historical
- [Omnichannel Sentinel Specification.txt](./Omnichannel%20Sentinel%20Specification.txt) — the original project specification (kept for reference).

## Suggested reading paths

- **"I want to run it"** → Developer's Guide → the OAuth/FCM setup docs → Troubleshooting.
- **"I want to understand the design"** → Architecture → Backend Guide → LLM Triage → Knowledge Base RAG.
- **"I'm reviewing the security model"** → Token Lifecycle & Security → Google OAuth → Discord.
- **"I'm non-technical"** → Non-Technical Setup Guide (+ Glossary).
