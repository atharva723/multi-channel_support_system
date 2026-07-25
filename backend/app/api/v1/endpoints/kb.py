"""Knowledge-base endpoints (RAG).

Tenant-scoped management of an account's knowledge base:

  * ``POST /kb/documents``  — upload a file (PDF/DOCX/TXT/MD); parsed, then
    chunked + embedded in the background.
  * ``POST /kb/ingest``     — ingest raw text (used by n8n auto-ingestion of
    external sources such as a website / Notion / Drive).
  * ``GET /kb/documents``   — list the account's documents with status.
  * ``DELETE /kb/documents/{id}`` — remove a document and its chunks.

Embedding runs in a FastAPI background task with its own DB session so the upload
response returns immediately while the document is processed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentAccount, DBSession
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.account import Account
from app.schemas.kb import KbDocumentOut, KbIngestIn, KbWebsiteIn
from app.services import kb as kb_service
from app.services.documents import DocumentParseError, extract_text
from app.services.web_scraper import WebScrapeError

router = APIRouter(prefix="/kb", tags=["knowledge-base"])

logger = logging.getLogger("sentinel.kb")


async def _process_in_background(document_id: int, text: str) -> None:
    """Background embed job with its own session (request session is closed)."""
    async with AsyncSessionLocal() as db:
        await kb_service.process_document_text(db, document_id=document_id, text=text)


async def _process_website_in_background(document_id: int, url: str) -> None:
    """Background crawl + embed job with its own session."""
    async with AsyncSessionLocal() as db:
        await kb_service.process_website(db, document_id=document_id, url=url)


@router.post(
    "/documents",
    response_model=KbDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a knowledge-base document (PDF/DOCX/TXT/MD)",
)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> KbDocumentOut:
    text = await _read_and_extract(file)

    doc = await kb_service.create_document(
        db,
        account_id=account.id,
        title=file.filename or "Untitled document",
        content_type=file.content_type,
        source="upload",
        source_ref=None,
    )
    background.add_task(_process_in_background, doc.id, text)
    return KbDocumentOut.model_validate(doc)


async def _read_and_extract(file: UploadFile) -> str:
    """Read an uploaded file, enforce limits, and extract its text."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > settings.kb_max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large (max "
                f"{settings.kb_max_upload_bytes // (1024 * 1024)} MB)."
            ),
        )
    try:
        text = extract_text(
            data=data,
            filename=file.filename or "document",
            content_type=file.content_type,
        )
    except DocumentParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not text.strip():
        raise HTTPException(
            status_code=400, detail="No readable text found in the document."
        )
    return text


@router.post(
    "/documents/{document_id}/replace",
    response_model=KbDocumentOut,
    summary="Replace an uploaded document's content in place (overwrite)",
)
async def replace_document(
    document_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> KbDocumentOut:
    text = await _read_and_extract(file)
    doc = await kb_service.reset_document_for_replace(
        db,
        account_id=account.id,
        document_id=document_id,
        title=file.filename or "Untitled document",
        content_type=file.content_type,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Uploaded document not found.")
    background.add_task(_process_in_background, doc.id, text)
    return KbDocumentOut.model_validate(doc)


@router.post(
    "/ingest",
    response_model=KbDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw text into the knowledge base (n8n auto-ingestion)",
)
async def ingest_text(
    payload: KbIngestIn,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> KbDocumentOut:
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="`text` must not be empty.")
    doc = await kb_service.ingest_text(
        db,
        account_id=account.id,
        title=payload.title or (payload.source_ref or "Synced source"),
        text=payload.text,
        source=payload.source,
        source_ref=payload.source_ref,
    )
    return KbDocumentOut.model_validate(doc)


@router.post(
    "/sources",
    response_model=KbDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a website source (crawled + embedded in the background)",
)
async def add_website(
    payload: KbWebsiteIn,
    background: BackgroundTasks,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> KbDocumentOut:
    try:
        doc = await kb_service.create_website_source(
            db, account_id=account.id, url=payload.url
        )
    except WebScrapeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background.add_task(
        _process_website_in_background, doc.id, doc.source_ref or payload.url
    )
    return KbDocumentOut.model_validate(doc)


@router.post(
    "/sources/{document_id}/resync",
    response_model=KbDocumentOut,
    summary="Re-crawl a website source and re-embed it",
)
async def resync_source(
    document_id: int,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> KbDocumentOut:
    doc = await kb_service.resync_document(
        db, account_id=account.id, document_id=document_id
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Website source not found.")
    return KbDocumentOut.model_validate(doc)


@router.post(
    "/sources/resync-all",
    summary="Re-crawl every website source for the account (n8n scheduler)",
)
async def resync_all_sources(
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> dict[str, int]:
    synced = await kb_service.resync_all_web(db, account_id=account.id)
    return {"synced": synced}


@router.get(
    "/documents",
    response_model=list[KbDocumentOut],
    summary="List the account's knowledge-base documents",
)
async def list_documents(
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> list[KbDocumentOut]:
    docs = await kb_service.list_documents(db, account_id=account.id)
    return [KbDocumentOut.model_validate(d) for d in docs]


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge-base document",
)
async def delete_document(
    document_id: int,
    account: Account = CurrentAccount,
    db: AsyncSession = DBSession,
) -> None:
    ok = await kb_service.delete_document(
        db, account_id=account.id, document_id=document_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
