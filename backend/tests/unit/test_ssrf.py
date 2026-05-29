"""SSRF guardrail tests."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from app.guardrails.ssrf import URLValidationError, validate_url, validate_url_shape


@contextmanager
def _patched_dns(addresses: list[str]) -> Iterator[None]:
    """Patch `getaddrinfo` to return the given IPs for any host."""
    fake = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0)) for ip in addresses]
    with patch("app.guardrails.ssrf.socket.getaddrinfo", return_value=fake):
        yield


@pytest.mark.unit
def test_blocks_non_http_schemes() -> None:
    for url in ("file:///etc/passwd", "ftp://example.com", "javascript:alert(1)"):
        with pytest.raises(URLValidationError, match="http or https"):
            validate_url(url)


@pytest.mark.unit
def test_blocks_metadata_ip_literal() -> None:
    with pytest.raises(URLValidationError, match="metadata"):
        validate_url("http://169.254.169.254/latest/meta-data/")


@pytest.mark.unit
def test_blocks_host_that_resolves_to_metadata_ip() -> None:
    with _patched_dns(["169.254.169.254"]):
        with pytest.raises(URLValidationError):
            validate_url("https://metadata.example.com")


@pytest.mark.unit
def test_blocks_private_ips() -> None:
    for ip in ("10.0.0.1", "192.168.1.1", "172.16.0.1"):
        with _patched_dns([ip]):
            with pytest.raises(URLValidationError, match="private"):
                validate_url("https://internal.example.com")


@pytest.mark.unit
def test_blocks_loopback_and_link_local() -> None:
    with _patched_dns(["127.0.0.1"]):
        with pytest.raises(URLValidationError, match="loopback"):
            validate_url("https://localhost.example.com")
    with _patched_dns(["169.254.42.42"]):
        with pytest.raises(URLValidationError):
            validate_url("https://link.example.com")


@pytest.mark.unit
def test_rejects_empty_or_too_long() -> None:
    with pytest.raises(URLValidationError, match="empty"):
        validate_url("")
    with pytest.raises(URLValidationError, match="length"):
        validate_url("https://example.com/" + "a" * 3000)


@pytest.mark.unit
def test_validate_url_shape_without_dns() -> None:
    assert validate_url_shape("https://example.com/path") == "https://example.com/path"
    with pytest.raises(URLValidationError, match="http or https"):
        validate_url_shape("ftp://example.com")
    with pytest.raises(URLValidationError, match="no host"):
        validate_url_shape("https://")


@pytest.mark.unit
def test_accepts_public_url() -> None:
    with _patched_dns(["93.184.216.34"]):  # example.com
        assert validate_url("https://example.com/blog/post") == "https://example.com/blog/post"
