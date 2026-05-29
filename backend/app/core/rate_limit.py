"""slowapi rate limiting."""

from __future__ import annotations

from typing import Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import ACCESS_TOKEN_COOKIE, decode_access_token


def _user_or_ip_key(request: Request) -> str:
    """Rate-limit key: authenticated user id, else client IP."""
    settings = request.app.state.settings
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token:
        payload = decode_access_token(token, settings)
        if payload is not None:
            return f"user:{payload.sub}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_user_or_ip_key)


def login_rate_limit() -> Callable:
    return limiter.limit("5/minute", key_func=get_remote_address)


def create_run_hourly_limit() -> Callable:
    return limiter.limit("5/hour")


def create_run_daily_limit() -> Callable:
    return limiter.limit("20/day")
