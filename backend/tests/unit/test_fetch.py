"""URL fetch + extraction tests.

These run entirely against in-memory httpx transports — no network. We focus
on the guardrail behaviours: size cap, content-type filtering, timeout, and
that valid HTML is reduced to readable plain text.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest

from app.ai.fetch import MAX_BYTES, FetchError, fetch_url


@contextmanager
def _bypass_ssrf() -> Iterator[None]:
    """Replace `validate_url` to skip DNS resolution in unit tests."""
    with patch("app.ai.fetch.validate_url", side_effect=lambda u, **_: u):
        yield


def _mock_transport(
    status: int = 200,
    body: bytes = b"<html><body>hi</body></html>",
    content_type: str = "text/html",
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": content_type},
        )

    return httpx.MockTransport(handler)


@contextmanager
def _patched_client(transport: httpx.MockTransport) -> Iterator[None]:
    """Patch httpx.AsyncClient so fetch_url uses our mock transport."""
    real = httpx.AsyncClient

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    with patch("app.ai.fetch.httpx.AsyncClient", side_effect=factory):
        yield


@pytest.mark.unit
async def test_fetch_extracts_article_text() -> None:
    html = b"""
    <html><head><title>Hello Title</title></head><body>
      <nav>nav</nav>
      <article>
        <h1>Big news</h1>
        <p>Here is a paragraph of useful content that is long enough to clear the minimum body length check by quite a comfortable margin so the fetch path accepts it.</p>
        <p>Here is more content. It also discusses the topic at hand in some detail, which gives trafilatura plenty of substance to extract.</p>
      </article>
      <footer>footer</footer>
    </body></html>
    """
    with _bypass_ssrf(), _patched_client(_mock_transport(body=html)):
        result = await fetch_url("https://example.com/post")
    assert "useful content" in result.cleaned_text
    assert "nav" not in result.cleaned_text
    assert "footer" not in result.cleaned_text
    assert result.content_hash and len(result.content_hash) == 64


@pytest.mark.unit
async def test_fetch_truncates_oversized_response() -> None:
    article = (
        b"<article><h1>Big news</h1><p>"
        + b"Useful content " * 30
        + b"</p></article>"
    )
    big = b"<html><body>" + article + b"x" * (MAX_BYTES + 10) + b"</body></html>"
    with _bypass_ssrf(), _patched_client(_mock_transport(body=big)):
        result = await fetch_url("https://example.com/big")
    assert "Useful content" in result.cleaned_text
    assert result.bytes_fetched == MAX_BYTES


@pytest.mark.unit
async def test_fetch_rejects_non_text_content_type() -> None:
    with _bypass_ssrf(), _patched_client(_mock_transport(content_type="image/png")):
        with pytest.raises(FetchError, match="content-type"):
            await fetch_url("https://example.com/image.png")


@pytest.mark.unit
async def test_fetch_rejects_4xx() -> None:
    with _bypass_ssrf(), _patched_client(_mock_transport(status=404, body=b"")):
        with pytest.raises(FetchError, match="HTTP 404"):
            await fetch_url("https://example.com/missing")


@pytest.mark.unit
async def test_fetch_retries_after_timeout() -> None:
    html = b"""
    <html><head><title>Retry OK</title></head><body>
      <article><p>"""
    html += b"Retry succeeded with enough content for the minimum body length check. " * 3
    html += b"""</p></article>
    </body></html>
    """
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("slow host")
        return httpx.Response(200, content=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    with _bypass_ssrf(), _patched_client(transport):
        with patch("app.ai.fetch.get_settings") as settings:
            settings.return_value = type(
                "S",
                (),
                {
                    "FETCH_CONNECT_TIMEOUT": 5.0,
                    "FETCH_READ_TIMEOUT": 5.0,
                    "FETCH_MAX_RETRIES": 2,
                    "FETCH_RETRY_BACKOFF_SECONDS": 0.0,
                },
            )()
            result = await fetch_url("https://example.com/slow")

    assert calls["n"] == 2
    assert "Retry succeeded" in result.cleaned_text


@pytest.mark.unit
async def test_fetch_urls_parallel_uses_shared_client() -> None:
    html = b"""
    <html><head><title>Parallel</title></head><body>
      <article><p>"""
    html += b"Parallel fetch content with enough length for validation. " * 4
    html += b"""</p></article></body></html>
    """
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host or "")
        return httpx.Response(200, content=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        with _bypass_ssrf(), patch("app.ai.fetch.get_settings") as settings:
            settings.return_value = type(
                "S",
                (),
                {
                    "FETCH_CONNECT_TIMEOUT": 5.0,
                    "FETCH_READ_TIMEOUT": 5.0,
                    "FETCH_MAX_RETRIES": 0,
                    "FETCH_RETRY_BACKOFF_SECONDS": 0.0,
                },
            )()
            from app.ai.fetch import fetch_urls_parallel

            out = await fetch_urls_parallel(
                [
                    "https://a.example.com/page",
                    "https://b.example.com/page",
                    "https://c.example.com/page",
                ],
                concurrency=3,
                client=client,
            )

    assert len(out) == 3
    assert all(not isinstance(v, FetchError) for v in out.values())
    assert len(calls) == 3


@pytest.mark.unit
async def test_fetch_rejects_empty_body() -> None:
    html = b"<html><body></body></html>"
    with _bypass_ssrf(), _patched_client(_mock_transport(body=html)):
        with pytest.raises(FetchError, match="empty"):
            await fetch_url("https://example.com/empty")
