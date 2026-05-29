"""FastAPI application entry point."""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import Settings, get_settings
from app.core.llm_logger import setup_llm_logger
from app.core.rate_limit import limiter
from app.db.models import AppEvent
from app.db.session import get_session_factory
from app.obs.logging import configure_logging
from app.obs.middleware import ObservabilityMiddleware

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings)
    setup_llm_logger()
    if settings.LOG_LEVEL == "DEBUG":
        log.info(
            "demo_credentials",
            user="demo-user@example.com / demo-user-pass",
            admin="demo-admin@example.com / demo-admin-pass",
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Market Research Intelligence Assistant",
        version="0.2.0",
        description=(
            "Hybrid AI research pipeline: deterministic URL extraction + agentic topic "
            "search, with independent LLM-as-judge verification."
        ),
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ObservabilityMiddleware)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        tb = traceback.format_exc()
        log.error("unhandled_exception", path=request.url.path, error=str(exc))
        await _persist_exception_event(request, exc, tb)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    from app.api.admin import router as admin_router
    from app.api.auth import router as auth_router
    from app.api.health import router as health_router
    from app.api.runs import router as runs_router
    from app.api.sources import router as sources_router

    # Health at root for Container Apps probes; app API under /api for SWA linked backend.
    app.include_router(health_router)
    api = APIRouter(prefix="/api")
    api.include_router(auth_router)
    api.include_router(runs_router)
    api.include_router(sources_router)
    api.include_router(admin_router)
    app.include_router(api)

    return app


async def _persist_exception_event(
    request: Request, exc: Exception, tb: str
) -> None:
    payload: dict[str, Any] = {
        "path": request.url.path,
        "method": request.method,
        "error": str(exc),
        "traceback": tb[-8000:],
    }
    user_id = None
    from app.core.security import ACCESS_TOKEN_COOKIE, decode_access_token

    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token:
        settings: Settings = request.app.state.settings
        payload_dec = decode_access_token(token, settings)
        if payload_dec is not None:
            user_id = payload_dec.sub

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(
                AppEvent(
                    kind="exception",
                    user_id=user_id,
                    payload=payload,
                )
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("failed to persist exception event", error=str(e))


app = create_app()
