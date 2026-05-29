"""URL / SSRF validation guardrail.

Blocks:
  - Non-http(s) schemes
  - Hostnames that resolve to private, loopback, link-local, or reserved IPs
  - The Azure / EC2 metadata IP `169.254.169.254` (link-local but blocked
    explicitly so the intent is obvious from the code).

This runs BEFORE httpx fetches anything, so a malicious URL can never reach
the network. We resolve every A/AAAA record returned by `getaddrinfo` rather
than just the first — defeats trivial DNS rebinding for the initial lookup
(a follow-up rebind during fetch is mitigated by httpx's connection reuse).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = frozenset({"http", "https"})
METADATA_IP = "169.254.169.254"


class URLValidationError(ValueError):
    """Raised when a URL fails an SSRF / shape check."""


def validate_url_shape(raw: str, *, max_length: int = 2048) -> str:
    """Shape-only URL check (no DNS). Used at the API boundary on create."""
    if not raw or not raw.strip():
        raise URLValidationError("URL is empty")
    raw = raw.strip()
    if len(raw) > max_length:
        raise URLValidationError(f"URL exceeds maximum length of {max_length}")

    try:
        parsed = urlparse(raw)
    except Exception as e:  # urlparse is forgiving but be defensive
        raise URLValidationError(f"unparseable URL: {e}") from e

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise URLValidationError("use http or https")

    host = parsed.hostname
    if not host:
        raise URLValidationError("URL has no host")

    return raw


def validate_url(raw: str, *, max_length: int = 2048) -> str:
    """Validate `raw` and return a canonical URL string.

    Raises `URLValidationError` with a human-readable reason on any failure.
    """
    raw = validate_url_shape(raw, max_length=max_length)
    host = urlparse(raw).hostname
    assert host  # guaranteed by validate_url_shape

    # Block direct numeric metadata IP before even attempting DNS resolution.
    if host == METADATA_IP:
        raise URLValidationError("metadata IP is not allowed")

    # Resolve every record. `getaddrinfo` raises on unknown hosts.
    try:
        addrs = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise URLValidationError(f"could not resolve host {host!r}: {e}") from e

    for _fam, _type, _proto, _canon, sockaddr in addrs:
        ip_str = sockaddr[0]
        # IPv6 addresses can carry zone ids like "fe80::1%en0"; strip them.
        ip_str = ip_str.partition("%")[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise URLValidationError(f"resolved to unparseable IP {ip_str!r}") from None
        # Order matters: 127.0.0.1 and 169.254.x.x both match `is_private`,
        # so check the more specific categories first for clearer errors.
        if ip_str == METADATA_IP:
            raise URLValidationError("host resolves to metadata IP")
        if ip.is_loopback:
            raise URLValidationError(f"host resolves to loopback IP {ip}")
        if ip.is_link_local:
            raise URLValidationError(f"host resolves to link-local IP {ip}")
        if ip.is_reserved or ip.is_unspecified or ip.is_multicast:
            raise URLValidationError(f"host resolves to reserved/special IP {ip}")
        if ip.is_private:
            raise URLValidationError(f"host resolves to private IP {ip}")

    return raw
