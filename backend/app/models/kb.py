"""Knowledge base models (RAG).

Per-tenant knowledge base used to ground AI replies. A :class:`KbDocument` is one
source (an uploaded file or an externally-synced source such as a website), and a
:class:`KbChunk` is one embedded text passage from it. Everything is scoped to an
``account_id`` so tenants are fully isolated — retrieval only ever searches the
caller's own chunks.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KbDocument(Base):
    """One knowledge-base source for an account (uploaded file or synced source)."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        # A given external source (per account) maps to a single document so
        # re-syncing updates it in place instead of duplicating.
        UniqueConstraint(
            "account_id", "source", "source_ref", name="uq_kb_account_source_ref"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Where this document came from: "upload", "web", "notion", "gdrive", ...
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="upload")
    # External identity for synced sources (URL / page id). NULL for uploads.
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Processing lifecycle: "processing" -> "ready" | "failed".
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing"
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Total chunks to embed (known once the text is chunked). Drives a real
    # progress bar: chunk_count / chunk_total while status == "processing".
    chunk_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["KbChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<KbDocument id={self.id} account_id={self.account_id} "
            f"source={self.source!r} status={self.status!r}>"
        )


class KbChunk(Base):
    """One embedded text passage of a knowledge-base document."""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Denormalized for fast tenant-scoped retrieval without a join.
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Embedding stored as a JSON array of floats (portable across SQLite). The
    # model name is kept so a future embedding-model swap can re-embed cleanly.
    embedding: Mapped[str] = mapped_column(Text, nullable=False)
    embed_model: Mapped[str] = mapped_column(String(80), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    document: Mapped["KbDocument"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<KbChunk id={self.id} doc={self.document_id} "
            f"idx={self.chunk_index}>"
        )
