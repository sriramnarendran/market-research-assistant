"""Integration tests for auth flows."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_signup_login_me_and_protected_route(authed_client: AsyncClient) -> None:
    me = await authed_client.get("/api/auth/me")
    assert me.status_code == 200
    assert "@" in me.json()["email"]

    runs = await authed_client.post(
        "/api/runs",
        json={"topics": ["cloud security"], "urls": []},
    )
    assert runs.status_code == 201


@pytest.mark.integration
async def test_login_wrong_password(client: AsyncClient) -> None:
    email = f"bad-{uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "good-password-1"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert r.status_code == 401


@pytest.mark.integration
async def test_signup_duplicate_no_enumeration(client: AsyncClient) -> None:
    email = f"dup-{uuid4().hex[:8]}@example.com"
    first = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password-1234"},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "password-5678"},
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Unable to create account"


@pytest.mark.integration
async def test_unauthenticated_runs_rejected(client: AsyncClient) -> None:
    r = await client.get("/api/runs")
    assert r.status_code == 401
