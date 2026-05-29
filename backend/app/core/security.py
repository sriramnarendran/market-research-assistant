"""Password hashing and JWT helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings

ACCESS_TOKEN_COOKIE = "access_token"
_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class TokenPayload:
    sub: UUID
    email: str
    role: str


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(
    *,
    user_id: UUID,
    email: str,
    role: str,
    settings: Settings,
) -> str:
    now = datetime.now(UTC)
    exp = now + timedelta(hours=settings.JWT_TTL_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> TokenPayload | None:
    try:
        data = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return TokenPayload(
            sub=UUID(str(data["sub"])),
            email=str(data["email"]),
            role=str(data["role"]),
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def cookie_max_age_seconds(settings: Settings) -> int:
    return settings.JWT_TTL_HOURS * 3600
