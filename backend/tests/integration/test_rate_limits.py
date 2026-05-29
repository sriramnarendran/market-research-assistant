"""Rate limit integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_login_rate_limit_triggers(client: AsyncClient) -> None:
    email = f"rl-{uuid4().hex[:8]}@example.com"
    password = "rate-limit-pw"
    await client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
    )

    last_status = 200
    for _ in range(7):
        r = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "wrong"},
        )
        last_status = r.status_code

    assert last_status == 429
