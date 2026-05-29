"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health() -> HealthResponse:
    """Liveness probe — returns 200 if the process is up."""
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/health/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Readiness probe — checks downstream config is present.

    Does not call out to Azure / Tavily / DB; only verifies env config is wired so
    we fail fast on a misconfigured deployment.
    """
    settings = get_settings()
    checks = {
        "azure_openai_configured": bool(
            settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_KEY
        ),
        "main_deployment_set": bool(settings.AZURE_OPENAI_MAIN_DEPLOYMENT),
        "judge_deployment_set": bool(settings.AZURE_OPENAI_JUDGE_DEPLOYMENT),
        "tavily_configured": bool(settings.TAVILY_API_KEY),
        "database_url_set": bool(settings.DATABASE_URL),
    }
    overall = all(checks.values()) or settings.LLM_MODE == "test"
    return ReadyResponse(status="ok" if overall else "degraded", checks=checks)
