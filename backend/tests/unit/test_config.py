"""Settings normalization tests."""

import pytest

from app.core.config import (
    Settings,
    get_settings,
    is_direct_supabase_database_url,
    validate_database_url_or_exit,
)


def test_database_url_normalizes_postgresql_scheme() -> None:
    s = Settings(
        DATABASE_URL="postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
        JWT_SECRET="x" * 32,
    )
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")
    assert "ssl=require" in s.DATABASE_URL


def test_database_url_preserves_asyncpg_driver() -> None:
    url = "postgresql+asyncpg://postgres:secret@localhost:5432/market_research"
    s = Settings(DATABASE_URL=url, JWT_SECRET="x" * 32)
    assert s.DATABASE_URL == url


def test_database_url_rejects_pooler_with_plain_postgres_user() -> None:
    with pytest.raises(ValueError, match="postgres.<project-ref>"):
        Settings(
            DATABASE_URL=(
                "postgresql://postgres:secret@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
            ),
            JWT_SECRET="x" * 32,
        )


def test_database_url_pooler_username_preserved() -> None:
    s = Settings(
        DATABASE_URL=(
            "postgresql://postgres.gjsvdretsksgycrugrfx:%5BHeyProgress-2026-assignment%5D"
            "@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
        ),
        JWT_SECRET="x" * 32,
    )
    assert "postgres.gjsvdretsksgycrugrfx" in s.DATABASE_URL
    assert "ssl=require" in s.DATABASE_URL


def test_is_direct_supabase_database_url() -> None:
    assert is_direct_supabase_database_url(
        "postgresql+asyncpg://postgres:secret@db.abc.supabase.co:5432/postgres"
    )
    assert not is_direct_supabase_database_url(
        "postgresql+asyncpg://postgres.abc:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )


def test_validate_skips_outside_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONTAINER_APP_NAME", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:secret@db.abc.supabase.co:5432/postgres",
    )
    validate_database_url_or_exit()  # no exit locally


def test_validate_exits_in_container_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTAINER_APP_NAME", "mra-app-container")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:secret@db.abc.supabase.co:5432/postgres",
    )
    get_settings.cache_clear()
    with pytest.raises(SystemExit) as exc:
        validate_database_url_or_exit()
    assert exc.value.code == 1
