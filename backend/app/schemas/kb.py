"""Schemas for the knowledge base (RAG)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class KbDocumentOut(BaseModel):
    """A knowledge-base document as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content_type: Optional[str] = None
    source: str
    source_ref: Optional[str] = None
    status: str
    chunk_count: int
    chunk_total: int = 0
    error: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()


class KbIngestIn(BaseModel):
    """Text-ingestion body (used by n8n auto-ingestion workflows)."""

    title: str
    text: str
    source: str = "web"
    source_ref: Optional[str] = None


class KbWebsiteIn(BaseModel):
    """Add-a-website body: the app posts a URL to crawl into the KB."""

    url: str
