"""Unit tests for password hashing and JWT."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(JWT_SECRET="test-secret-key-32-bytes-minimum!!")


def test_hash_and_verify_password() -> None:
    h = hash_password("correct horse battery")
    assert verify_password(h, "correct horse battery")
    assert not verify_password(h, "wrong")


def test_jwt_round_trip(settings: Settings) -> None:
    uid = UUID("11111111-1111-1111-1111-111111111111")
    token = create_access_token(
        user_id=uid, email="a@b.com", role="user", settings=settings
    )
    payload = decode_access_token(token, settings)
    assert payload is not None
    assert payload.sub == uid
    assert payload.email == "a@b.com"
    assert payload.role == "user"


def test_jwt_rejects_bad_token(settings: Settings) -> None:
    assert decode_access_token("not.a.jwt", settings) is None
