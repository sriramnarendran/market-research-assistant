"""Application settings, loaded from environment via pydantic-settings."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


def is_direct_supabase_database_url(url: str) -> bool:
    """True for db.<project>.supabase.co (IPv6-only; fails on Azure Container Apps)."""
    return "@db." in url and ".supabase.co" in url and "pooler.supabase.com" not in url


def _is_ipv4_only_cloud_host() -> bool:
    """Hosts that typically lack IPv6 egress (Azure Container Apps, App Service, etc.)."""
    return bool(
        os.getenv("CONTAINER_APP_NAME")
        or os.getenv("WEBSITE_SITE_NAME")
        or os.getenv("K_SERVICE")
    )


def validate_database_url_or_exit() -> None:
    """Fail fast in cloud when a direct Supabase URL is used (IPv6-only)."""
    if not _is_ipv4_only_cloud_host():
        return
    settings = get_settings()
    if not is_direct_supabase_database_url(settings.DATABASE_URL):
        return
    if settings.ALLOW_DIRECT_SUPABASE_URL:
        return
    print(
        "\nERROR: DATABASE_URL uses Supabase direct host db.<project>.supabase.co.\n"
        "That endpoint is IPv6-only and Azure Container Apps cannot reach it "
        "(Network is unreachable).\n\n"
        "Fix: Supabase Dashboard → Project Settings → Database → Connection string\n"
        "Copy the **Session pooler** URI (host *.pooler.supabase.com, port 5432).\n"
        "User format: postgres.<project-ref>  (not just postgres)\n\n"
        "Update Azure:\n"
        "  export DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres'\n"
        "  ./infra/azure/deploy.sh <resource-group>   # or update the Container App secret\n\n"
        "To override this check (IPv4 add-on on direct connection): ALLOW_DIRECT_SUPABASE_URL=true\n",
        file=sys.stderr,
    )
    sys.exit(1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Azure OpenAI — single provider for both the main pipeline and the judge.
    # Point MAIN and JUDGE at different deployments to recover model-family
    # independence (e.g. main=gpt-5, judge=gpt-5-mini). Default to the same
    # deployment for the simplest single-model setup.
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2025-04-01-preview"
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_MAIN_DEPLOYMENT: str = "gpt-5-mini"
    AZURE_OPENAI_JUDGE_DEPLOYMENT: str = "gpt-5-mini"

    # Tavily
    TAVILY_API_KEY: str = ""
    # Web search publish window in days (default 90 ≈ 3 months). Passed as Tavily ``days``.
    TAVILY_SEARCH_DAYS: int = Field(default=90, ge=0, le=365)
    # Fallback when TAVILY_SEARCH_DAYS=0: day | week | month | year
    TAVILY_TIME_RANGE: Literal["day", "week", "month", "year"] | None = None

    # Database — Postgres via SQLAlchemy asyncpg. Production: Supabase (see .env.example).
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/market_research"
    )
    # Allow db.<project>.supabase.co direct URLs (IPv6-only; not for Azure Container Apps).
    ALLOW_DIRECT_SUPABASE_URL: bool = False

    # AI mode — "live" hits real endpoints, "test" uses Pydantic AI TestModel
    LLM_MODE: Literal["live", "test"] = "live"

    # Per-run token budget across all phases
    PER_RUN_TOKEN_BUDGET: int = Field(default=200_000, ge=10_000, le=2_000_000)

    # Tokens held back from extract/research/synth for the judge phase.
    JUDGE_BUDGET_RESERVE: int = Field(default=50_000, ge=0, le=500_000)

    # Pipeline concurrency caps. The pipeline parallelises HTTP fetches and
    # per-source LLM extract calls under these semaphores. Keep small enough
    # to stay under Azure OpenAI tokens-per-minute quotas; raise if your
    # deployment has plenty of headroom and you want lower latency.
    FETCH_CONCURRENCY: int = Field(default=5, ge=1, le=20)
    EXTRACT_CONCURRENCY: int = Field(default=5, ge=1, le=20)
    JUDGE_CONCURRENCY: int = Field(default=5, ge=1, le=20)
    # Parallel Tavily + agent research tasks (one asyncio task per user keyword).
    RESEARCH_CONCURRENCY: int = Field(default=3, ge=1, le=10)

    # HTTP fetch for user-supplied URLs (and full-article hydration for research hits).
    FETCH_CONNECT_TIMEOUT: float = Field(default=20.0, ge=5.0, le=120.0)
    FETCH_READ_TIMEOUT: float = Field(default=45.0, ge=10.0, le=180.0)
    FETCH_MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    FETCH_RETRY_BACKOFF_SECONDS: float = Field(default=1.5, ge=0.0, le=30.0)

    # Cap LLM extract calls per run (user URLs first, then top-scored research).
    MAX_EXTRACT_SOURCES: int = Field(default=8, ge=1, le=30)
    # Cap facts returned per source (output_validator trims excess).
    MAX_FACTS_PER_SOURCE: int = Field(default=12, ge=1, le=20)

    # Auth (Phase 2)
    JWT_SECRET: str = "change-me"
    JWT_TTL_HOURS: int = 24
    AUTH_DEV_BYPASS: bool = True
    AUTH_COOKIE_SECURE: bool = False
    PERSIST_REQUEST_EVENTS: bool = True

    # CORS
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173"

    # Dev fallback user id (used in Phase 1 when no auth header is sent)
    DEV_USER_ID: UUID = UUID("00000000-0000-0000-0000-000000000001")

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Per-LLM-call transcript log — one JSON line per agent.run() containing the
    # full message graph (system prompt, user prompt, tool calls, tool returns,
    # model output). Set to "" (empty) to disable. Path is resolved relative to
    # the backend working directory if not absolute.
    LLM_LOG_FILE: str = "logs/llm_requests.jsonl"
    LLM_LOG_MAX_BYTES: int = Field(default=50_000_000, ge=0)  # 50 MB per file
    LLM_LOG_BACKUP_COUNT: int = Field(default=5, ge=0)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @field_validator("LLM_MODE", mode="before")
    @classmethod
    def _normalize_llm_mode(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _normalize_database_url(cls, url: str) -> str:
        """Normalize scheme/driver, decode/re-encode credentials, add Supabase SSL."""
        if url.startswith("postgres://"):
            url = "postgresql://" + url.removeprefix("postgres://")

        parse_target = url
        if parse_target.startswith("postgresql+asyncpg://"):
            parse_target = "postgresql://" + parse_target.removeprefix("postgresql+asyncpg://")
        elif parse_target.startswith("postgresql+psycopg2://"):
            parse_target = "postgresql://" + parse_target.removeprefix("postgresql+psycopg2://")
        elif not parse_target.startswith("postgresql://"):
            return url

        parsed = make_url(parse_target)
        query = dict(parsed.query)
        host = parsed.host or ""

        if "supabase.co" in host and "ssl" not in query:
            query["ssl"] = "require"

        if "pooler.supabase.com" in host and parsed.username == "postgres":
            raise ValueError(
                "Supabase pooler requires username postgres.<project-ref>, not 'postgres'. "
                "Copy the Session pooler URI from Supabase Dashboard → Settings → Database."
            )

        rebuilt = URL.create(
            drivername="postgresql+asyncpg",
            username=parsed.username,
            password=parsed.password,
            host=parsed.host,
            port=parsed.port,
            database=parsed.database,
            query=query,
        )
        return rebuilt.render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
