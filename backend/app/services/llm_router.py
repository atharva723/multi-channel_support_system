"""LLM Router Engine (Ollama-backed, production).

This is the "sentiment brain" from the specification. It performs two jobs
against a locally running Ollama model (default ``llama3.2``):

1. **Criticality classification** — computes the probability that a message is
   Critical, ``P(C=1|M)``. Rather than trusting a free-text answer, we ask the
   model to emit a single classification token and read the raw *token
   log-probabilities* Ollama returns. We then apply a softmax over the two
   class tokens exactly as the spec defines:

        P(C=1|M) = softmax(z)_critical
                 = exp(l_crit) / (exp(l_crit) + exp(l_info))

   where ``l_crit`` / ``l_info`` are the log-probabilities the model assigned to
   the "Critical" / "Informational" tokens at the classification position. This
   yields a calibrated, continuous probability (not a hard yes/no), which is what
   the urgency model and escalation threshold consume.

2. **Auto-reply drafting** — for non-critical tickets, generates a concise,
   friendly support reply that an agent can approve/modify or that n8n can send
   back through the originating channel.

Design notes:
  * A single ``httpx.AsyncClient`` is reused for connection pooling.
  * All failures raise ``LLMRouterError`` so the API layer can translate them
    into a clean 502 instead of leaking transport details.
  * The client is a singleton created lazily and closed on app shutdown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx

from app.core.config import settings

_OLLAMA_GENERATE = "/api/generate"

# Instruction that forces the model to answer with exactly one classification
# token so the first generated token carries the whole decision signal.
_CLASSIFY_PROMPT = (
    "You are a customer-support triage classifier. Read the support message "
    "below and decide whether it describes a CRITICAL problem (an outage, data "
    "loss, security issue, payment/checkout failure, blocking bug, or an angry "
    "customer at risk of churning) or is merely INFORMATIONAL (a question, "
    "feature request, thanks, or minor issue).\n\n"
    "Respond with exactly one word: either 'Critical' or 'Informational'.\n\n"
    "Support message:\n\"\"\"\n{content}\n\"\"\"\n\n"
    "Classification:"
)

_REPLY_PROMPT = (
    "You are a helpful, empathetic customer-support agent. Write a concise, "
    "friendly reply (2-4 sentences) to the customer message below. Address their "
    "concern directly, be reassuring, and do not invent specific facts, ticket "
    "numbers, or timelines you cannot know. Do not include a subject line or "
    "email headers.\n\n"
    "Customer ({author_name}) wrote:\n\"\"\"\n{content}\n\"\"\"\n\n"
    "Your reply:"
)

# Grounded variant: the model must answer ONLY from the provided knowledge-base
# context and must not invent anything beyond it.
_GROUNDED_REPLY_PROMPT = (
    "You are a helpful, empathetic customer-support agent for this business. "
    "Answer the customer using ONLY the business knowledge base context below. "
    "Do NOT use outside knowledge and do NOT invent facts, prices, policies, "
    "ticket numbers, or timelines. If the answer is fully contained in the "
    "context, reply concisely (2-4 sentences), warmly, and directly. Do not "
    "include a subject line or email headers.\n\n"
    "Business knowledge base context:\n\"\"\"\n{context}\n\"\"\"\n\n"
    "Customer ({author_name}) wrote:\n\"\"\"\n{content}\n\"\"\"\n\n"
    "Your reply:"
)

# Used when the customer's question is NOT covered by the knowledge base
# (out of scope): politely acknowledge and defer to a human teammate.
_OUT_OF_SCOPE_PROMPT = (
    "You are a helpful, empathetic customer-support agent. The customer's "
    "question is NOT covered by the business's available information, so you "
    "cannot answer it yourself. Write a short (1-2 sentences), warm reply that "
    "acknowledges their message, does NOT attempt to answer or guess, and "
    "reassures them that a team member will follow up shortly. Do not include a "
    "subject line or email headers.\n\n"
    "Customer ({author_name}) wrote:\n\"\"\"\n{content}\n\"\"\"\n\n"
    "Your reply:"
)


class LLMRouterError(RuntimeError):
    """Raised when the LLM backend is unreachable or returns an unusable payload."""


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of a criticality classification."""

    criticality: float  # P(C=1|M) in [0, 1]
    label: str  # "Critical" | "Informational"
    raw_token: str  # the top token the model actually emitted


class LLMRouter:
    """Async client wrapping the Ollama generate API for triage."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_host,
            timeout=settings.ollama_timeout,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    # -- Public API --------------------------------------------------------
    async def classify_criticality(self, content: str) -> ClassificationResult:
        """Compute ``P(C=1|M)`` for a message via classification-token logprobs."""
        payload = {
            "model": settings.ollama_model,
            "prompt": _CLASSIFY_PROMPT.format(content=content.strip()),
            "stream": False,
            "logprobs": True,
            "top_logprobs": settings.llm_top_logprobs,
            "options": {
                "temperature": 0,
                "num_predict": 1,
            },
        }
        data = await self._post(payload)

        distribution = self._first_token_distribution(data)
        crit_logprob, info_logprob = self._extract_class_logprobs(distribution)
        criticality = self._softmax_critical(crit_logprob, info_logprob)

        raw_token = (data.get("response") or "").strip()
        label = "Critical" if criticality >= settings.criticality_threshold else "Informational"
        return ClassificationResult(
            criticality=round(criticality, 6),
            label=label,
            raw_token=raw_token,
        )

    async def generate_draft_reply(
        self,
        *,
        content: str,
        author_name: str,
        context: list[str] | None = None,
        out_of_scope: bool = False,
    ) -> str:
        """Generate a conversational auto-reply draft for a support message.

        Three modes:
          * ``out_of_scope=True`` — the KB has nothing relevant; politely defer
            to a human without attempting an answer.
          * ``context`` non-empty — ground the reply strictly in the provided
            knowledge-base passages.
          * neither — the account has no KB; behave as a general assistant.
        """
        if out_of_scope:
            prompt = _OUT_OF_SCOPE_PROMPT.format(
                content=content.strip(), author_name=author_name
            )
        elif context:
            joined = "\n\n---\n\n".join(context)
            prompt = _GROUNDED_REPLY_PROMPT.format(
                context=joined.strip(),
                content=content.strip(),
                author_name=author_name,
            )
        else:
            prompt = _REPLY_PROMPT.format(
                content=content.strip(), author_name=author_name
            )

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": settings.llm_reply_temperature,
                "num_predict": settings.llm_reply_max_tokens,
            },
        }
        data = await self._post(payload)
        reply = (data.get("response") or "").strip()
        if not reply:
            raise LLMRouterError("LLM returned an empty draft reply.")
        return reply

    # -- Internals ---------------------------------------------------------
    async def _post(self, payload: dict) -> dict:
        """POST to Ollama's generate endpoint and return the decoded JSON."""
        try:
            resp = await self._client.post(_OLLAMA_GENERATE, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:  # non-2xx from Ollama
            raise LLMRouterError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:  # transport/timeout/connection errors
            raise LLMRouterError(f"Could not reach Ollama: {exc}") from exc

    @staticmethod
    def _first_token_distribution(data: dict) -> list[dict]:
        """Return the ``top_logprobs`` distribution for the first generated token.

        Ollama places per-token logprobs under ``logprobs``; depending on
        version this is a single object (one token) or a list of them. We take
        the first token's ``top_logprobs`` candidate list.
        """
        logprobs = data.get("logprobs")
        if logprobs is None:
            raise LLMRouterError(
                "Ollama response did not include logprobs; ensure the server "
                "version supports 'logprobs' on /api/generate."
            )

        first = logprobs[0] if isinstance(logprobs, list) else logprobs
        candidates = first.get("top_logprobs") if isinstance(first, dict) else None
        if not candidates:
            # Fall back to the single chosen token if no alternatives were given.
            if isinstance(first, dict) and "token" in first and "logprob" in first:
                return [{"token": first["token"], "logprob": first["logprob"]}]
            raise LLMRouterError("Ollama response contained no usable token logprobs.")
        return candidates

    @staticmethod
    def _extract_class_logprobs(
        distribution: list[dict],
    ) -> tuple[float, float]:
        """Pull the log-probs of the Critical and Informational class tokens.

        Matching is prefix- and case-insensitive so tokenizer variants
        ("Critical", " Critical", "Information", "Informational") map correctly.
        The most probable (highest logprob) match for each class is used. A
        missing class is treated as a very low log-probability floor so softmax
        still yields a sane result.
        """
        floor = -30.0
        crit: float | None = None
        info: float | None = None

        for item in distribution:
            token = str(item.get("token", "")).strip().lower()
            if not token:
                continue
            logprob = float(item.get("logprob", floor))
            if token.startswith("crit"):
                crit = logprob if crit is None else max(crit, logprob)
            elif token.startswith("inform"):
                info = logprob if info is None else max(info, logprob)

        if crit is None and info is None:
            raise LLMRouterError(
                "Neither 'Critical' nor 'Informational' appeared in the model's "
                "token distribution; classification is undefined."
            )
        return (crit if crit is not None else floor, info if info is not None else floor)

    @staticmethod
    def _softmax_critical(crit_logprob: float, info_logprob: float) -> float:
        """Softmax over the two class logits, returning the Critical probability."""
        # Subtract the max for numerical stability before exponentiating.
        top = max(crit_logprob, info_logprob)
        exp_crit = math.exp(crit_logprob - top)
        exp_info = math.exp(info_logprob - top)
        return exp_crit / (exp_crit + exp_info)


# -- Singleton lifecycle ---------------------------------------------------
_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    """Return the process-wide ``LLMRouter`` singleton, creating it on first use."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


async def close_llm_router() -> None:
    """Close and reset the singleton (called from the app lifespan on shutdown)."""
    global _router
    if _router is not None:
        await _router.aclose()
        _router = None
