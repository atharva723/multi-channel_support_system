"""Website ingestion for the knowledge base.

Two steps, both here:

  * **Crawl** — starting from a URL, discover related same-domain pages (via the
    site's ``sitemap.xml`` and by following on-page links), prioritizing pages
    whose path looks like support/policy content. Bounded by ``kb_web_max_pages``.
  * **Scrape** — for each page, extract the clean *main content* text with
    ``trafilatura`` (drops nav/header/footer/scripts/ads — the "noise").

Returns one combined, de-duplicated text blob for the source, which the KB
pipeline then chunks + embeds like any other document.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

from app.core.config import settings

logger = logging.getLogger("sentinel.kb.web")


class WebScrapeError(RuntimeError):
    """Raised when a website could not be fetched or yielded no usable text."""


def normalize_url(url: str) -> str:
    """Add a scheme if missing and strip fragments; validate it's http(s)."""
    url = (url or "").strip()
    if not url:
        raise WebScrapeError("Empty URL.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise WebScrapeError(f"Invalid URL: {url!r}")
    # Drop the fragment; keep query (some sites route content via query).
    return parsed._replace(fragment="").geturl()


def _same_domain(a: str, b: str) -> bool:
    return urlparse(a).netloc.lower().lstrip("www.") == urlparse(b).netloc.lower().lstrip("www.")


def _priority_keywords() -> list[str]:
    return [k.strip().lower() for k in settings.kb_web_priority_keywords.split(",") if k.strip()]


def _fetch(client: httpx.Client, url: str) -> str | None:
    """Fetch a URL's HTML; returns None on any error or non-HTML response."""
    try:
        resp = client.get(url)
        if resp.status_code >= 400:
            return None
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "xml" not in ctype and ctype:
            return None
        return resp.text
    except httpx.HTTPError:
        return None


def _sitemap_urls(client: httpx.Client, base_url: str) -> list[str]:
    """Best-effort: pull same-domain page URLs from /sitemap.xml (one level)."""
    parsed = urlparse(base_url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    xml = _fetch(client, sitemap_url)
    if not xml:
        return []
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml, re.IGNORECASE)
    # If it's a sitemap index (points to other sitemaps), fetch the first few.
    out: list[str] = []
    nested = [u for u in locs if u.lower().endswith(".xml")]
    if nested:
        for sm in nested[:3]:
            child = _fetch(client, sm)
            if child:
                out.extend(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", child, re.IGNORECASE))
    else:
        out = locs
    return [u for u in out if _same_domain(u, base_url)]


def _links_from_html(html: str, base_url: str) -> list[str]:
    """Extract same-domain absolute links from a page's HTML."""
    hrefs = re.findall(r'href=["\']([^"\'#]+)["\']', html, re.IGNORECASE)
    out: list[str] = []
    for href in hrefs:
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        absolute = urlparse(absolute)._replace(fragment="").geturl()
        if absolute.startswith("http") and _same_domain(absolute, base_url):
            out.append(absolute)
    return out


def _rank(urls: list[str], keywords: list[str]) -> list[str]:
    """Order URLs so support/policy-looking paths come first; de-duplicate."""
    seen: set[str] = set()
    priority: list[str] = []
    rest: list[str] = []
    for u in urls:
        key = u.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        path = urlparse(u).path.lower()
        if any(kw in path for kw in keywords):
            priority.append(u)
        else:
            rest.append(u)
    return priority + rest


def _dedupe_lines(text: str) -> str:
    """Drop consecutive/again-repeated identical non-trivial lines."""
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) < 12:
            out.append(line)  # keep short lines (headings, table rows) as-is
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        out.append(line)
    return "\n".join(out)


def crawl_site(url: str, *, max_pages: int | None = None) -> tuple[str, list[str]]:
    """Crawl + scrape a website into one clean text blob.

    Returns ``(combined_text, pages_used)``. Raises :class:`WebScrapeError` if the
    start page can't be fetched or nothing usable was extracted.
    """
    start = normalize_url(url)
    max_pages = max_pages or settings.kb_web_max_pages
    keywords = _priority_keywords()

    headers = {"User-Agent": settings.kb_web_user_agent, "Accept": "text/html,*/*"}
    with httpx.Client(
        timeout=settings.kb_web_timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        start_html = _fetch(client, start)
        if not start_html:
            raise WebScrapeError(
                f"Could not fetch {start} (site may be down or blocking requests)."
            )

        # Build the candidate page set: start page + sitemap + on-page links.
        candidates = [start]
        candidates.extend(_sitemap_urls(client, start))
        candidates.extend(_links_from_html(start_html, start))
        ordered = _rank(candidates, keywords)
        # Always keep the start page first.
        ordered = [start] + [u for u in ordered if u.rstrip("/") != start.rstrip("/")]
        ordered = ordered[:max_pages]

        parts: list[str] = []
        used: list[str] = []
        for page in ordered:
            html = start_html if page == start else _fetch(client, page)
            if not html:
                continue
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
                url=page,
            )
            if extracted and extracted.strip():
                parts.append(extracted.strip())
                used.append(page)

    if not parts:
        raise WebScrapeError(
            f"Fetched {start} but could not extract any readable content."
        )

    combined = _dedupe_lines("\n\n".join(parts))
    return combined, used
