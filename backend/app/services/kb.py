"""Knowledge-base ingestion + retrieval (RAG core).

Shared by both KB input paths — mobile file upload and n8n text ingestion — so
there is a single chunk -> embed -> store pipeline. Retrieval embeds a query and
ranks the account's chunks by cosine similarity, returning the most relevant
passages used to ground AI replies.
"""

from __future__ import annotations

import asyncio
import json
import logging

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.kb import KbChunk, KbDocument
from app.services.documents import chunk_text
from app.services.embeddings import EmbeddingError, get_embedding_client
from app.services.web_scraper import WebScrapeError, crawl_site, normalize_url

logger = logging.getLogger("sentinel.kb")


async def create_document(
    db: AsyncSession,
    *,
    account_id: int,
    title: str,
    content_type: str | None,
    source: str,
    source_ref: str | None,
) -> KbDocument:
    """Create (or reset) a KB document row in the ``processing`` state.

    For synced sources (a non-null ``source_ref``) an existing document with the
    same (account, source, source_ref) is reused and its old chunks cleared, so
    re-syncing updates in place instead of duplicating.
    """
    doc: KbDocument | None = None
    if source_ref is not None:
        doc = (
            await db.scalars(
                select(KbDocument).where(
                    KbDocument.account_id == account_id,
                    KbDocument.source == source,
                    KbDocument.source_ref == source_ref,
                )
            )
        ).first()

    if doc is not None:
        await db.execute(delete(KbChunk).where(KbChunk.document_id == doc.id))
        doc.title = title
        doc.content_type = content_type
        doc.status = "processing"
        doc.chunk_count = 0
        doc.chunk_total = 0
        doc.error = None
    else:
        doc = KbDocument(
            account_id=account_id,
            title=title,
            content_type=content_type,
            source=source,
            source_ref=source_ref,
            status="processing",
            chunk_count=0,
            chunk_total=0,
        )
        db.add(doc)

    await db.commit()
    await db.refresh(doc)
    return doc


async def process_document_text(
    db: AsyncSession, *, document_id: int, text: str
) -> None:
    """Chunk + embed ``text`` and store the chunks for a document.

    Records progress incrementally (``chunk_total`` then a rising ``chunk_count``)
    so a poller can render a real progress bar. Marks the document ``ready`` on
    success or ``failed`` (with the error) if embedding fails.
    """
    doc = await db.get(KbDocument, document_id)
    if doc is None:
        return

    try:
        chunks = chunk_text(text)
        if not chunks:
            doc.status = "failed"
            doc.error = "No extractable text found in the document."
            doc.chunk_count = 0
            doc.chunk_total = 0
            await db.commit()
            return

        # Publish the total up front so the progress bar knows its denominator.
        doc.chunk_total = len(chunks)
        doc.chunk_count = 0
        await db.commit()

        client = get_embedding_client()
        stored = 0
        for index, chunk in enumerate(chunks):
            vector = await client.embed(settings.embed_document_prefix + chunk)
            db.add(
                KbChunk(
                    document_id=doc.id,
                    account_id=doc.account_id,
                    chunk_index=index,
                    text=chunk,
                    embedding=json.dumps(vector),
                    embed_model=settings.embed_model,
                )
            )
            stored += 1
            # Commit each chunk so pollers observe progress in near real time.
            doc.chunk_count = stored
            await db.commit()

        doc.status = "ready"
        doc.error = None
        await db.commit()
        logger.info("KB doc %s ready: %d chunks", doc.id, stored)
    except EmbeddingError as exc:
        await db.rollback()
        # Remove any partial chunks and mark the document failed.
        await db.execute(delete(KbChunk).where(KbChunk.document_id == document_id))
        doc = await db.get(KbDocument, document_id)
        if doc is not None:
            doc.status = "failed"
            doc.error = f"Embedding failed: {exc}"
            doc.chunk_count = 0
            await db.commit()
        logger.warning("KB doc %s failed: %s", document_id, exc)


async def ingest_text(
    db: AsyncSession,
    *,
    account_id: int,
    title: str,
    text: str,
    source: str,
    source_ref: str | None = None,
    content_type: str | None = None,
) -> KbDocument:
    """Create a document and process it inline (used by the n8n text endpoint)."""
    doc = await create_document(
        db,
        account_id=account_id,
        title=title,
        content_type=content_type,
        source=source,
        source_ref=source_ref,
    )
    await process_document_text(db, document_id=doc.id, text=text)
    await db.refresh(doc)
    return doc


async def create_website_source(
    db: AsyncSession, *, account_id: int, url: str
) -> KbDocument:
    """Create (or reset) a ``web`` KB document for a URL, in ``processing`` state.

    The actual crawl+embed happens in :func:`process_website` (slow; run it as a
    background task). Upserts by the normalized URL so re-adding refreshes it.
    """
    normalized = normalize_url(url)
    return await create_document(
        db,
        account_id=account_id,
        title=f"Website: {normalized}",
        content_type="text/html",
        source="web",
        source_ref=normalized,
    )


async def process_website(db: AsyncSession, *, document_id: int, url: str) -> None:
    """Crawl + scrape a website, then chunk + embed it for a document.

    The crawl (httpx + trafilatura) is synchronous, so it runs in a worker thread
    to avoid blocking the event loop. Marks the document ``failed`` with the error
    if the site can't be fetched or yields no content.
    """
    try:
        combined, pages = await asyncio.to_thread(crawl_site, url)
        logger.info("KB web doc %s crawled %d page(s)", document_id, len(pages))
    except WebScrapeError as exc:
        doc = await db.get(KbDocument, document_id)
        if doc is not None:
            doc.status = "failed"
            doc.error = str(exc)
            doc.chunk_count = 0
            await db.commit()
        logger.warning("KB web doc %s failed: %s", document_id, exc)
        return

    await process_document_text(db, document_id=document_id, text=combined)


async def resync_document(
    db: AsyncSession, *, account_id: int, document_id: int
) -> KbDocument | None:
    """Re-crawl + re-embed a ``web`` document. Returns None if not found/eligible."""
    doc = await db.get(KbDocument, document_id)
    if doc is None or doc.account_id != account_id or doc.source != "web":
        return None
    url = doc.source_ref
    if not url:
        return None
    await db.execute(delete(KbChunk).where(KbChunk.document_id == doc.id))
    doc.status = "processing"
    doc.chunk_count = 0
    doc.error = None
    await db.commit()
    await process_website(db, document_id=doc.id, url=url)
    await db.refresh(doc)
    return doc


async def resync_all_web(db: AsyncSession, *, account_id: int) -> int:
    """Re-crawl every ``web`` source for an account. Returns how many were synced."""
    docs = (
        await db.scalars(
            select(KbDocument).where(
                KbDocument.account_id == account_id, KbDocument.source == "web"
            )
        )
    ).all()
    count = 0
    for doc in docs:
        result = await resync_document(db, account_id=account_id, document_id=doc.id)
        if result is not None:
            count += 1
    return count


async def delete_document(db: AsyncSession, *, account_id: int, document_id: int) -> bool:
    """Delete a document (and its chunks) if it belongs to the account."""
    doc = await db.get(KbDocument, document_id)
    if doc is None or doc.account_id != account_id:
        return False
    await db.delete(doc)  # cascade removes chunks
    await db.commit()
    return True


async def reset_document_for_replace(
    db: AsyncSession,
    *,
    account_id: int,
    document_id: int,
    title: str,
    content_type: str | None,
) -> KbDocument | None:
    """Prepare an existing upload document to be overwritten with new content.

    Clears the old chunks and returns the row to a ``processing`` state (same id,
    so it stays in place in the list) ready for re-embedding. Returns None if the
    document isn't found, isn't owned by the account, or isn't an upload.
    """
    doc = await db.get(KbDocument, document_id)
    if doc is None or doc.account_id != account_id or doc.source != "upload":
        return None
    await db.execute(delete(KbChunk).where(KbChunk.document_id == doc.id))
    doc.title = title
    doc.content_type = content_type
    doc.status = "processing"
    doc.chunk_count = 0
    doc.chunk_total = 0
    doc.error = None
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(db: AsyncSession, *, account_id: int) -> list[KbDocument]:
    """List an account's KB documents, newest first."""
    rows = (
        await db.scalars(
            select(KbDocument)
            .where(KbDocument.account_id == account_id)
            .order_by(KbDocument.id.desc())
        )
    ).all()
    return list(rows)


async def account_has_kb(db: AsyncSession, *, account_id: int) -> bool:
    """True if the account has at least one embedded KB chunk."""
    row = (
        await db.execute(
            select(KbChunk.id).where(KbChunk.account_id == account_id).limit(1)
        )
    ).first()
    return row is not None


async def retrieve(
    db: AsyncSession,
    *,
    account_id: int,
    query: str,
    k: int | None = None,
    min_score: float | None = None,
) -> list[str]:
    """Return the account's most relevant KB passages for ``query``.

    Embeds the query and ranks the account's ready chunks by cosine similarity,
    returning up to ``k`` passages that clear ``min_score``. An empty list means
    the KB has nothing relevant (out of scope) — or the account has no KB.
    """
    k = k or settings.kb_top_k
    min_score = settings.kb_min_score if min_score is None else min_score

    rows = (
        await db.execute(
            select(KbChunk.text, KbChunk.embedding).where(
                KbChunk.account_id == account_id
            )
        )
    ).all()
    if not rows:
        return []

    try:
        query_vec = np.asarray(
            await get_embedding_client().embed(settings.embed_query_prefix + query),
            dtype=np.float32,
        )
    except EmbeddingError as exc:
        logger.warning("KB retrieval embed failed for account %s: %s", account_id, exc)
        return []

    q_norm = float(np.linalg.norm(query_vec))
    if q_norm == 0.0:
        return []

    scored: list[tuple[float, str]] = []
    for text, embedding_json in rows:
        try:
            vec = np.asarray(json.loads(embedding_json), dtype=np.float32)
        except (ValueError, TypeError):
            continue
        v_norm = float(np.linalg.norm(vec))
        if v_norm == 0.0 or vec.shape != query_vec.shape:
            continue
        score = float(np.dot(query_vec, vec) / (q_norm * v_norm))
        if score >= min_score:
            scored.append((score, text))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _, text in scored[:k]]
