"""Pytest configuration: force LLM_MODE=test for the whole suite."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("LLM_MODE", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/market_research",
)
os.environ.setdefault("LLM_LOG_FILE", "")


@pytest.fixture(autouse=True)
def _ensure_test_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "test")
    monkeypatch.setenv("LLM_LOG_FILE", "")
    monkeypatch.setenv("PERSIST_REQUEST_EVENTS", "false")
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture(scope="session")
def _db_ready() -> None:
    """Apply migrations and seed demo users on the test database."""
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(__file__))
    env = {**os.environ}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "app.db.seed"],
        cwd=root,
        env=env,
        check=True,
    )


@pytest.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch, _db_ready: None
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("AUTH_DEV_BYPASS", "false")
    monkeypatch.setenv("PERSIST_REQUEST_EVENTS", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """Client with a fresh signed-up user session cookie."""
    email = f"test-{uuid4().hex[:12]}@example.com"
    password = "test-password-8"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    yield client
