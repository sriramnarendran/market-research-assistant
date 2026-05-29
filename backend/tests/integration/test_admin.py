"""Admin endpoint gating tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_non_admin_forbidden(authed_client: AsyncClient) -> None:
    r = await authed_client.get("/api/admin/metrics/overview")
    assert r.status_code == 403


@pytest.mark.integration
async def test_admin_overview_ok(client: AsyncClient) -> None:
    login = await client.post(
        "/api/auth/login",
        json={
            "email": "demo-admin@example.com",
            "password": "demo-admin-pass",
        },
    )
    assert login.status_code == 200
    r = await client.get("/api/admin/metrics/overview")
    assert r.status_code == 200
    data = r.json()
    assert "total_users" in data
    assert data["total_users"] >= 1
    assert data["active_users_7d"] <= data["total_users"]
