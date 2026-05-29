"""URL path: validate → fetch (streaming, capped) → extract main content → truncate.

Each step is small and pure so it's easy to unit-test in isolation. The whole
thing runs inside the URL leg of the pipeline before any LLM is invoked.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.guardrails.ssrf import URLValidationError, validate_url
from app.llm.token_counter import estimate_tokens, truncate_to_token_budget

log = logging.getLogger(__name__)

# Limits — kept here so it's obvious what defends the fetch path.
MAX_BYTES = 500 * 1024
MAX_REDIRECTS = 3
PER_SOURCE_TOKEN_CAP = 80_000
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml")

# Browser-like headers — many sites block or slow bot User-Agents.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})


class FetchError(Exception):
    """Raised when a URL cannot be fetched or cleaned to usable text."""


@dataclass(slots=True)
class FetchedSource:
    """Result of fetching one URL."""

    url: str
    title: str | None
    cleaned_text: str
    content_hash: str
    bytes_fetched: int
    token_estimate: int


async def fetch_url(url: str, *, client: httpx.AsyncClient | None = None) -> FetchedSource:
    """Validate, fetch, extract, and truncate one URL.

    Pass a shared *client* when fetching many URLs in parallel (connection reuse).

    Raises `FetchError` (with a human-readable reason) on any failure. The
    caller decides whether a single failure aborts the run or is skipped.
    """
    try:
        canonical = validate_url(url)
    except URLValidationError as e:
        raise FetchError(f"invalid url: {e}") from e

    raw, content_type, body_bytes = await _stream_get(canonical, client=client)
    if not any(t in content_type for t in ALLOWED_CONTENT_TYPES):
        raise FetchError(f"unsupported content-type {content_type!r}")

    title, body = _extract_article(raw)
    if not body or len(body.strip()) < 100:
        raise FetchError("extracted body was empty or too short to be useful")

    capped = truncate_to_token_budget(body, PER_SOURCE_TOKEN_CAP)
    digest = hashlib.sha256(capped.encode("utf-8", errors="ignore")).hexdigest()

    return FetchedSource(
        url=canonical,
        title=title,
        cleaned_text=capped,
        content_hash=digest,
        bytes_fetched=body_bytes,
        token_estimate=estimate_tokens(capped),
    )


async def fetch_urls_parallel(
    urls: list[str],
    *,
    concurrency: int,
    client: httpx.AsyncClient | None = None,
) -> dict[str, FetchedSource | FetchError]:
    """Fetch many URLs concurrently with a shared HTTP client."""
    if not urls:
        return {}

    limit = max(1, min(concurrency, len(urls)))
    sem = asyncio.Semaphore(limit)

    async def _run(http: httpx.AsyncClient) -> dict[str, FetchedSource | FetchError]:
        async def _one(input_url: str) -> tuple[str, FetchedSource | FetchError]:
            async with sem:
                try:
                    return input_url, await fetch_url(input_url, client=http)
                except FetchError as e:
                    return input_url, e

        pairs = await asyncio.gather(*[_one(u) for u in urls])
        return dict(pairs)

    if client is not None:
        return await _run(client)
    async with fetch_http_client() as owned:
        return await _run(owned)


@asynccontextmanager
async def fetch_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Shared AsyncClient for parallel URL fetches (connection pooling)."""
    async with httpx.AsyncClient(
        timeout=_fetch_timeout(),
        max_redirects=MAX_REDIRECTS,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    ) as client:
        yield client


# -----------------------------------------------------------------------------
# Internals
# -----------------------------------------------------------------------------


def _fetch_timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(
        connect=settings.FETCH_CONNECT_TIMEOUT,
        read=settings.FETCH_READ_TIMEOUT,
        write=15.0,
        pool=15.0,
    )


def _is_retryable(err: FetchError) -> bool:
    msg = str(err).lower()
    if "timeout" in msg:
        return True
    if any(f"http {code}" in msg for code in _RETRYABLE_HTTP):
        return True
    if "http error" in msg and any(
        token in msg for token in ("connect", "reset", "closed", "timed out")
    ):
        return True
    return False


async def _stream_get(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, str, int]:
    """Issue a streaming GET with retries for slow or flaky hosts."""
    settings = get_settings()
    attempts = settings.FETCH_MAX_RETRIES + 1
    last_err: FetchError | None = None

    for attempt in range(attempts):
        if attempt > 0:
            delay = settings.FETCH_RETRY_BACKOFF_SECONDS * attempt
            log.info("retrying fetch for %s in %.1fs (attempt %d/%d)", url, delay, attempt + 1, attempts)
            await asyncio.sleep(delay)
        try:
            if client is not None:
                return await _stream_get_once(url, client)
            async with fetch_http_client() as owned:
                return await _stream_get_once(url, owned)
        except FetchError as e:
            last_err = e
            if attempt + 1 >= attempts or not _is_retryable(e):
                raise
            log.warning("fetch attempt %d/%d failed for %s: %s", attempt + 1, attempts, url, e)

    assert last_err is not None
    raise last_err


async def _stream_get_once(url: str, client: httpx.AsyncClient) -> tuple[str, str, int]:
    """Single streaming GET attempt; stop reading once MAX_BYTES is reached."""
    try:
        async with client.stream("GET", url) as resp:
            if resp.status_code in _RETRYABLE_HTTP:
                raise FetchError(f"HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise FetchError(f"HTTP {resp.status_code}")
            content_type = resp.headers.get("content-type", "").lower()
            if not any(t in content_type for t in ALLOWED_CONTENT_TYPES):
                raise FetchError(f"unsupported content-type {content_type!r}")

            chunks: list[bytes] = []
            total = 0
            truncated = False
            async for chunk in resp.aiter_bytes(64 * 1024):
                if total >= MAX_BYTES:
                    truncated = True
                    break
                remaining = MAX_BYTES - total
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    total = MAX_BYTES
                    truncated = True
                    break
                chunks.append(chunk)
                total += len(chunk)

            if truncated:
                log.warning(
                    "truncated fetch for %s at %d bytes (response larger than cap)",
                    url,
                    MAX_BYTES,
                )

            encoding = resp.encoding or "utf-8"
            body = b"".join(chunks).decode(encoding, errors="replace")
            return body, content_type, total
    except httpx.TimeoutException as e:
        raise FetchError("fetch timeout") from e
    except httpx.ConnectError as e:
        raise FetchError(f"connection failed: {e}") from e
    except httpx.HTTPError as e:
        raise FetchError(f"http error: {e}") from e


def _extract_article(html: str) -> tuple[str | None, str]:
    """Extract main content with trafilatura, fall back to BeautifulSoup."""
    title: str | None = None
    body: str = ""

    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
            output_format="txt",
        )
        if extracted:
            body = extracted

        meta = trafilatura.extract_metadata(html)
        if meta is not None:
            title = (
                meta.title if hasattr(meta, "title") and meta.title else None
            )
    except Exception as e:  # noqa: BLE001
        log.warning("trafilatura failed, falling back to bs4: %s", e)

    if not body:
        body = _bs4_fallback(html)
    if not title:
        title = _bs4_title(html)

    return title, body.strip()


def _bs4_fallback(html: str) -> str:
    """Last-resort text extraction — strip script/style and return visible text."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside"]):
        tag.decompose()
    # Prefer <article> or <main> when present
    target = soup.find("article") or soup.find("main") or soup.body or soup
    return target.get_text(separator="\n", strip=True)


def _bs4_title(html: str) -> str | None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return None
