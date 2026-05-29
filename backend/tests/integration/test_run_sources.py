"""Integration tests for run source listing during pipeline progress."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import Run, Source
from app.db.session import get_session_factory


@pytest.mark.asyncio
async def test_list_run_sources_empty(authed_client: AsyncClient) -> None:
    r = await authed_client.post(
        "/api/runs",
        json={"topics": ["cloud storage"], "urls": []},
    )
    assert r.status_code == 201
    run_id = r.json()["id"]

    listed = await authed_client.get(f"/api/runs/{run_id}/sources")
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_list_run_sources_returns_rows(authed_client: AsyncClient) -> None:
    r = await authed_client.post(
        "/api/runs",
        json={"topics": [], "urls": ["https://example.com/news"]},
    )
    assert r.status_code == 201
    run_id = r.json()["id"]

    factory = get_session_factory()
    async with factory() as session:
        session.add(
            Source(
                run_id=run_id,
                url="https://example.com/news",
                origin="url_path",
                title="Example headline",
                fetched_text="Some article text",
                content_hash="abc123",
                bytes=128,
            )
        )
        await session.commit()

    listed = await authed_client.get(f"/api/runs/{run_id}/sources")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["url"] == "https://example.com/news"
    assert body[0]["title"] == "Example headline"
    assert body[0]["origin"] == "url_path"


@pytest.mark.asyncio
async def test_list_run_sources_not_found(authed_client: AsyncClient) -> None:
    r = await authed_client.get(f"/api/runs/{uuid4()}/sources")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_run_sources_other_user_forbidden(authed_client: AsyncClient, client: AsyncClient) -> None:
    created = await authed_client.post("/api/runs", json={"topics": ["x"], "urls": []})
    run_id = created.json()["id"]

    other = await client.post(
        "/api/auth/signup",
        json={"email": f"other-{uuid4().hex[:8]}@example.com", "password": "test-password-8"},
    )
    assert other.status_code == 201

    r = await client.get(f"/api/runs/{run_id}/sources")
    assert r.status_code == 404

    # sanity: run exists for owner
    factory = get_session_factory()
    async with factory() as session:
        row = (await session.execute(select(Run).where(Run.id == run_id))).scalar_one_or_none()
        assert row is not None
