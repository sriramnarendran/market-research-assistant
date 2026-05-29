"""HTTP request logging and app_events persistence."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import ACCESS_TOKEN_COOKIE, decode_access_token
from app.db.models import AppEvent
from app.db.session import get_session_factory

log = structlog.get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        user_id: str | None = None
        settings = request.app.state.settings
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
        if token:
            payload = decode_access_token(token, settings)
            if payload is not None:
                user_id = str(payload.sub)

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            path = request.url.path
            log.info(
                "http_request",
                method=request.method,
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                user_id=user_id,
            )
            settings = request.app.state.settings
            if settings.PERSIST_REQUEST_EVENTS and not path.startswith("/health"):
                await _persist_request_event(
                    method=request.method,
                    path=path,
                    status=status_code,
                    duration_ms=duration_ms,
                    user_id=user_id,
                )


async def _persist_request_event(
    *,
    method: str,
    path: str,
    status: int,
    duration_ms: int,
    user_id: str | None,
) -> None:
    payload: dict[str, Any] = {
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": duration_ms,
    }
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            from uuid import UUID

            session.add(
                AppEvent(
                    kind="request",
                    user_id=UUID(user_id) if user_id else None,
                    payload=payload,
                )
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001 — observability must not break requests
        log.warning("failed to persist app_event", error=str(e))
