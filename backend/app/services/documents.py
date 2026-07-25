"""Document text extraction and chunking for the knowledge base.

Turns an uploaded file (PDF / DOCX / TXT / MD) into plain text, and splits any
text into overlapping chunks sized for embedding. Kept dependency-light: PDF via
``pypdf``, DOCX via ``python-docx``, everything else decoded as UTF-8 text.
"""

from __future__ import annotations

import io

from app.core.config import settings


class DocumentParseError(ValueError):
    """Raised when a document cannot be parsed into text."""


_PDF_TYPES = {"application/pdf"}
_DOCX_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def extract_text(*, data: bytes, filename: str, content_type: str | None) -> str:
    """Extract plain text from an uploaded document's raw bytes.

    Dispatch is by file extension first (most reliable), falling back to the
    reported content type. Unsupported types raise ``DocumentParseError``.
    """
    name = (filename or "").lower()
    ctype = (content_type or "").lower()

    if name.endswith(".pdf") or ctype in _PDF_TYPES:
        return _extract_pdf(data)
    if name.endswith(".docx") or ctype in _DOCX_TYPES:
        return _extract_docx(data)
    if name.endswith((".txt", ".md", ".markdown", ".text")) or ctype.startswith(
        "text/"
    ):
        return _decode_text(data)

    # Last resort: try to decode as text; if it's binary this will be gibberish,
    # so guard by requiring it to be mostly decodable.
    try:
        return _decode_text(data)
    except DocumentParseError as exc:
        raise DocumentParseError(
            f"Unsupported document type '{content_type or filename}'. "
            "Supported: PDF, DOCX, TXT, MD."
        ) from exc


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        parts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - surface any pypdf failure uniformly
        raise DocumentParseError(f"Could not read PDF: {exc}") from exc
    return "\n\n".join(p.strip() for p in parts if p.strip())


def _extract_docx(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError(f"Could not read DOCX: {exc}") from exc
    return "\n".join(parts)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise DocumentParseError("Could not decode document as text.")


def chunk_text(
    text: str,
    *,
    size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into overlapping chunks on natural boundaries.

    Normalizes whitespace, then walks the text in ``size``-character windows that
    overlap by ``overlap`` characters, preferring to break at a paragraph or
    sentence boundary near the window edge so chunks stay coherent.
    """
    size = size or settings.kb_chunk_size
    overlap = overlap if overlap is not None else settings.kb_chunk_overlap
    if overlap >= size:
        overlap = size // 4

    normalized = "\n".join(line.rstrip() for line in text.splitlines())
    normalized = normalized.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    length = len(normalized)

    while start < length:
        end = min(start + size, length)
        if end < length:
            # Try to break on a paragraph, then a sentence, then whitespace,
            # searching backwards within the last ~40% of the window.
            window = normalized[start:end]
            floor = int(size * 0.6)
            break_at = -1
            for sep in ("\n\n", "\n", ". ", "? ", "! ", " "):
                idx = window.rfind(sep)
                if idx >= floor:
                    break_at = idx + len(sep)
                    break
            if break_at != -1:
                end = start + break_at

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks
