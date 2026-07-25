# Knowledge Base & RAG

> How Sentinel grounds AI replies in each business's own information — the RAG
> (Retrieval-Augmented Generation) pipeline, the two input paths (upload +
> website), append-vs-replace behavior, and the progress bar. Complements
> [LLM_TRIAGE_AND_SCORING.md](./LLM_TRIAGE_AND_SCORING.md).

## The idea

By default an LLM answers from its generic training. That's wrong for customer
support — it might invent a refund policy your business doesn't have. **RAG** fixes
this: before drafting a reply, we **retrieve** the most relevant passages from the
business's *own* uploaded knowledge and tell the model to answer **only** from
them. If nothing relevant is found, the AI **doesn't guess** — it politely says a
teammate will follow up.

## What "RAG" means here, concretely

```
        INGEST (once, per source)                 ANSWER (per incoming message)
  ┌────────────────────────────────┐        ┌────────────────────────────────────┐
  │ document / website              │        │ customer message                    │
  │   → extract clean text          │        │   → embed the question              │
  │   → split into ~700-char chunks │        │   → cosine-match against this        │
  │   → embed each (nomic-embed)    │        │      account's chunks (top-k)        │
  │   → store vectors in SQLite     │        │   → feed top passages to the LLM as  │
  │      (per account_id)           │        │      grounding context               │
  └────────────────────────────────┘        └────────────────────────────────────┘
```

## Storage (per-account, isolated)

Two tables (`app/models/kb.py`), both carrying `account_id`:
- **`kb_documents`** — one row per source: `title`, `source`
  (`upload` | `web`), `source_ref` (URL for websites, null for uploads),
  `status` (`processing` | `ready` | `failed`), `chunk_count`, `chunk_total`,
  `error`.
- **`kb_chunks`** — one row per embedded passage: `text`, `embedding` (JSON array
  of floats), `embed_model`, `chunk_index`, `account_id` (denormalized for fast
  tenant-scoped retrieval).

Retrieval is a **brute-force cosine** over the account's chunks with `numpy` —
plenty fast for the expected size (hundreds–low-thousands of chunks per tenant).
At larger scale you'd swap in `sqlite-vec`/FAISS behind the same `retrieve()`.

## Embeddings — `nomic-embed-text` (via Ollama)

- 768-dimensional vectors; prereq `ollama pull nomic-embed-text`.
- **Task prefixes matter:** this model expects `search_document: ` on stored
  chunks and `search_query: ` on queries. Using them improves the separation
  between relevant and irrelevant content (configurable via
  `embed_document_prefix` / `embed_query_prefix`).
- **Similarity threshold:** `kb_min_score` = **0.6**, calibrated against measured
  scores (in-scope questions land ~0.67–0.78, out-of-scope ~0.52–0.58). A query
  whose best chunk is below 0.6 is treated as **out of scope**.
- `kb_top_k` = 4 passages max fed as context.

## Two input paths (a user can use both)

### 1. File upload (private docs) — no n8n
`POST /kb/documents` (multipart). Backend parses **PDF** (`pypdf`), **DOCX**
(`python-docx`), or **TXT/MD** (`documents.py`), then chunks + embeds in a
background task. Best for internal docs that aren't on the public web.

### 2. Website (public policy/FAQ pages)
`POST /kb/sources { url }`. The **backend** does the work (`web_scraper.py`):
- **Crawl** — from the start URL, discover same-domain pages via `sitemap.xml`
  and on-page links, prioritizing support/policy paths (faq, refund, shipping,
  terms…), bounded by `kb_web_max_pages` (15).
- **Scrape** — extract each page's clean **main content** with `trafilatura`
  (drops nav, footer, ads, scripts), de-duplicate, combine, then chunk + embed.

> Websites are added **in the app** and crawled immediately. n8n's only role is an
> optional scheduler that re-crawls them periodically — see
> [../automation/n8n/README.md](../automation/n8n/README.md). Crawling never
> happens *in* n8n.

Both paths funnel into one shared pipeline: `services/kb.py` →
`create_document` → `process_document_text` (chunk → embed → store).

## Append vs. Replace vs. Refresh (important UX distinction)

| Action | Endpoint | Effect |
| --- | --- | --- |
| **Upload** | `POST /kb/documents` | **Appends** a new document (grow the KB). Each upload is separate. |
| **Replace** | `POST /kb/documents/{id}/replace` | **Overwrites that one uploaded doc in place** (same row/id, old chunks removed, re-embedded). For fixing an outdated/wrong doc — other docs untouched. |
| **Remove** | `DELETE /kb/documents/{id}` | Deletes a document and its chunks. |
| **Add website** | `POST /kb/sources` | Crawl a URL. Upserts by URL. |
| **Refresh / Resync** | `POST /kb/sources/{id}/resync`, `/kb/sources/resync-all` | Re-crawl website source(s), replacing their chunks in place. |

> **Why both append and replace exist:** users need *both* "add a bit more
> knowledge" (append) and "that document was wrong, swap it" (replace). Uploads
> default to append; per-document Replace handles overwrite. Website sources upsert
> by URL, so re-adding/re-syncing a URL updates in place instead of duplicating.

## Grounding at draft time (`triage.py` + `llm_router.py`)

For each incoming message the pipeline calls `kb.retrieve(account_id, message)`:

```
context = retrieve(...)
if context:                      → grounded prompt: "answer ONLY from this context…"
elif account_has_kb(...):        → out-of-scope prompt: "you don't have that info,
                                    a teammate will follow up" (no guessing)
else (no KB):                    → normal general reply
```

The grounded prompt explicitly forbids inventing facts, prices, policies, or
timelines beyond the provided context. Verified end-to-end: a coffee shop's
uploaded refund policy answers refund questions correctly, while an unrelated
"do you sell laptops?" gets the polite human-defer response.

## Progress bar (real, not fake)

Embedding runs in the background, so the app shows a **green progress bar** while a
document is `processing`. It's driven by **real** backend progress: the pipeline
publishes `chunk_total` up front, then commits `chunk_count` after each chunk. The
app polls (~1.2s) and renders `chunk_count / chunk_total`. Phases:
- `chunk_total == 0` → indeterminate sweep ("Reading website…" / "Preparing…").
- embedding → determinate % ("Embedding your data…").
- done → the **Ready** pill with the chunk count.

Component: `mobile/src/components/ProgressBar.tsx` (pure React Native `Animated`,
no native module — green fill + gliding sheen).

## Config knobs (`core/config.py`)
`kb_chunk_size` (700), `kb_chunk_overlap` (100), `kb_top_k` (4),
`kb_min_score` (0.6), `kb_max_upload_bytes` (10 MB), `kb_web_max_pages` (15),
`kb_web_timeout`, `kb_web_priority_keywords`, `embed_model`,
`embed_document_prefix` / `embed_query_prefix`.

## Endpoints
See [API_REFERENCE.md](./API_REFERENCE.md) for the `/kb/*` request/response shapes.
