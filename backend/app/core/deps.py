"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import ACCESS_TOKEN_COOKIE, TokenPayload, decode_access_token
from app.db.models import User
from app.db.session import get_session


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve user from JWT cookie, or dev bypass when enabled."""
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    payload: TokenPayload | None = None
    if token:
        payload = decode_access_token(token, settings)

    if payload is not None:
        result = await session.execute(select(User).where(User.id == payload.sub))
        user = result.scalar_one_or_none()
        if user is not None:
            return user

    if settings.AUTH_DEV_BYPASS:
        result = await session.execute(
            select(User).where(User.id == settings.DEV_USER_ID)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DBSession = Annotated[AsyncSession, Depends(get_session)]


def not_found(message: str = "not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
