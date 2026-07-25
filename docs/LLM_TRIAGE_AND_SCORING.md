# LLM Triage & Scoring

> How Sentinel decides whether a message is *critical* and how urgent it is over
> time — the local LLM setup, the log-probability trick behind `P(C=1|M)`, and the
> exponential urgency curve. RAG grounding of the reply is covered in
> [KNOWLEDGE_BASE_RAG.md](./KNOWLEDGE_BASE_RAG.md).

## Local LLM via Ollama

Everything runs **locally** through [Ollama](https://ollama.com) over HTTP — no
cloud LLM, no API keys, no per-token cost. Two models:

```powershell
ollama pull llama3.2          # criticality classification + reply drafting
ollama pull nomic-embed-text  # knowledge-base embeddings (see RAG doc)
```

Config: `SENTINEL_OLLAMA_HOST` (default `http://localhost:11434`),
`SENTINEL_OLLAMA_MODEL` (`llama3.2`). Client: `app/services/llm_router.py`.

## Criticality: `P(C=1|M)` from token log-probabilities

We want a **calibrated probability** that a message `M` is Critical, not just a
yes/no. The trick (in `LLMRouter.classify_criticality`):

1. Prompt the model to answer with **exactly one token** — either `Critical` or
   `Informational` — and request the token **log-probabilities** (`logprobs`,
   `top_logprobs`).
2. Read the log-probs the model assigned to the two class tokens at that position:
   `l_crit` and `l_info`.
3. Apply a **softmax over just those two logits**:

```
                       exp(l_crit)
   P(C=1|M) = ---------------------------------
               exp(l_crit) + exp(l_info)
```

This yields a smooth probability in `[0, 1]` (e.g. `0.93`), which is far more
useful than a hard label — it feeds both the escalation threshold *and* the
urgency seed. Token matching is prefix/case-insensitive (`crit*` / `inform*`) so
tokenizer variants map correctly; a missing class falls back to a low log-prob
floor so the softmax stays well-defined.

- **Escalation threshold:** `criticality_threshold` (default **0.8**). At/above →
  **ESCALATED** (goes to the mobile agent); below → **AUTO_REPLY**.

## Reply drafting

For every ticket the router also drafts a reply (`generate_draft_reply`). Three
modes, chosen in the triage pipeline based on the knowledge base:
- **Grounded** — relevant KB context found → answer strictly from it.
- **Out-of-scope** — a KB exists but nothing matched → politely defer to a human.
- **General** — no KB at all → normal helpful reply.

Details and prompts: [KNOWLEDGE_BASE_RAG.md](./KNOWLEDGE_BASE_RAG.md). Sampling:
`llm_reply_temperature` (0.4), `llm_reply_max_tokens` (220).

## Urgency: `U(t) = S0 · e^(λ_c · t)`

Criticality is a snapshot at arrival; **urgency grows while a ticket waits**. The
Desk ranks tickets by an *aged* urgency recomputed on read (`services/urgency.py`,
`endpoints/tickets.py`):

```
U(t) = S0 · exp(λ_c · t)
```

- **`S0`** (initial severity) is seeded from `P(C=1|M)` scaled by `severity_scale`
  (10.0) — so a fresh critical ticket already starts high.
- **`t`** is elapsed minutes since the message arrived.
- **`λ_c`** is a **per-channel** growth constant, because different channels carry
  different response expectations:
  - `lambda_discord` = 0.05 (fast, conversational)
  - `lambda_email`   = 0.01 (asynchronous, patient)

### Why exponential, not linear?
An SLA breach isn't linear — the "cost" of an unanswered critical ticket
accelerates the longer it sits (a 2-minute delay is fine; 2 hours is a crisis).
Exponential growth captures that: older unattended tickets **rise past** newer
ones on the Desk automatically, which is exactly the triage behavior you want. A
linear model would let a fresh medium-criticality ticket outrank an old critical
one for too long.

> Urgency is intentionally **recomputed on read**, not stored-and-stale, so
> ranking always reflects the true current wait time.

## End-to-end in the pipeline

```
message → classify_criticality → P(C=1|M)
        → (RAG) retrieve KB → generate_draft_reply
        → compute_urgency(P, channel, arrival) → U(t)
        → persist Ticket
        → P ≥ 0.8 ? escalate (SSE + push) : auto-reply
```

Source: `app/api/v1/endpoints/triage.py`, `app/services/llm_router.py`,
`app/services/urgency.py`.

## Failure handling

If Ollama is unreachable or returns an unusable payload, the router raises
`LLMRouterError` and `/triage` returns **502** (rather than leaking transport
errors). If Ollama isn't running, start it and pull the models — see
[TROUBLESHOOTING.md](./TROUBLESHOOTING.md).
