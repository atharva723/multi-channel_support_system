"""Ollama embeddings client.

Thin async wrapper over Ollama's ``/api/embeddings`` used by the knowledge-base
ingestion and retrieval paths. Kept separate from the ``LLMRouter`` (which does
generation) so the embedding model and its lifecycle are independent.
"""

from __future__ import annotations

import httpx

from app.core.config import settings

_EMBEDDINGS_PATH = "/api/embeddings"


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend is unreachable or returns no vector."""


class EmbeddingClient:
    """Async client wrapping the Ollama embeddings API."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_host,
            timeout=settings.embed_timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text."""
        payload = {"model": settings.embed_model, "prompt": text}
        try:
            resp = await self._client.post(_EMBEDDINGS_PATH, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(
                f"Ollama embeddings returned HTTP {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError(f"Could not reach Ollama embeddings: {exc}") from exc

        vector = data.get("embedding")
        if not vector or not isinstance(vector, list):
            raise EmbeddingError("Ollama embeddings response contained no vector.")
        return [float(x) for x in vector]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts sequentially (Ollama has no batch endpoint)."""
        return [await self.embed(t) for t in texts]


# -- Singleton lifecycle ---------------------------------------------------
_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """Return the process-wide embedding client, creating it on first use."""
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client


async def close_embedding_client() -> None:
    """Close and reset the singleton (called from the app lifespan on shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
