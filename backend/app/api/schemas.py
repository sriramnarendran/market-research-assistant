"""HTTP wire models for the FastAPI routes.

Keeps wire shapes separate from the domain types in `app/ai/schemas.py` so
we can evolve API responses independently of internal LLM-facing schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.guardrails.ssrf import URLValidationError, validate_url_shape

MAX_TOPICS = 3
MAX_URLS = 5
MAX_TOPIC_LEN = 120


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str


# -----------------------------------------------------------------------------
# Admin metrics
# -----------------------------------------------------------------------------


class AdminOverview(BaseModel):
    total_users: int
    active_users_7d: int
    total_runs: int
    runs_today: int
    completed_runs: int
    in_progress_runs: int
    failed_runs: int
    reports_generated: int
    total_sources: int
    url_sources: int
    search_sources: int
    sources_today: int


class UsageDayRow(BaseModel):
    day: str
    provider: str
    phase: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class RunMetrics(BaseModel):
    total_runs: int
    success_rate: float
    p50_duration_sec: float | None
    p95_duration_sec: float | None
    failure_breakdown: dict[str, int]


class UserUsageSummary(BaseModel):
    user_id: UUID
    email: str
    total_runs: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class AppErrorRow(BaseModel):
    id: UUID
    created_at: datetime
    payload: dict[str, Any]


class RunCreateRequest(BaseModel):
    """User-submitted run creation payload."""

    topics: list[str] = Field(default_factory=list, max_length=MAX_TOPICS)
    urls: list[str] = Field(default_factory=list, max_length=MAX_URLS)
    prior_run_id: UUID | None = Field(
        default=None,
        description="Phase 2: enables change-detection diffing against a prior run.",
    )

    @field_validator("topics", mode="after")
    @classmethod
    def _validate_topics(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in v:
            t = raw.strip()
            if not t:
                continue
            if len(t) > MAX_TOPIC_LEN:
                raise ValueError(f"topic exceeds {MAX_TOPIC_LEN} chars: {t[:20]}…")
            if any(c in t for c in ("\n", "\r", "\x00")):
                raise ValueError("topic contains illegal control characters")
            cleaned.append(t)
        return cleaned

    @field_validator("urls", mode="after")
    @classmethod
    def _validate_urls(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        errors: list[str] = []
        for raw in v:
            t = raw.strip()
            if not t:
                continue
            try:
                cleaned.append(validate_url_shape(t))
            except URLValidationError as e:
                errors.append(f"{t!r}: {e}")
        if errors:
            raise ValueError("Invalid URL(s) — " + "; ".join(errors))
        return cleaned


class RunSummary(BaseModel):
    """Compact run row for list views."""

    id: UUID
    status: str
    topics: list[str]
    urls: list[str]
    created_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    has_report: bool


class UrlFetchFailure(BaseModel):
    url: str
    error: str


class RunDetail(BaseModel):
    """Full run detail including the rendered report JSONB."""

    id: UUID
    status: str
    topics: list[str]
    urls: list[str]
    created_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
    url_fetch_failures: list[UrlFetchFailure] = Field(default_factory=list)
    report: dict[str, Any] | None = None


class SourceSummary(BaseModel):
    """Lightweight source row for live progress during a run."""

    id: UUID
    url: str
    origin: str
    title: str | None
    topic_match: str | None = None
    bytes: int
    fetched_at: datetime


class SourceDetail(BaseModel):
    """Raw source row — useful for debugging and the judge replay UX."""

    id: UUID
    run_id: UUID
    url: str
    origin: str
    title: str | None
    topic_match: str | None = None
    fetched_text: str
    bytes: int
    fetched_at: datetime


class RunCreateResponse(BaseModel):
    """Result of `POST /runs` — returned immediately, before pipeline runs."""

    id: UUID
    status: str
