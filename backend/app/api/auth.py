"""Authentication routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LoginRequest, SignupRequest, UserResponse
from app.core.config import Settings, get_settings
from app.core.deps import CurrentUser, get_current_user
from app.core.rate_limit import limiter
from app.db.session import get_session
from app.core.security import (
    ACCESS_TOKEN_COOKIE,
    cookie_max_age_seconds,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=cookie_max_age_seconds(settings),
    )


def _clear_auth_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
    )


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    payload: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    email = payload.email.strip().lower()
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create account",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    session.add(user)
    await session.flush()

    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        settings=settings,
    )
    _set_auth_cookie(response, token, settings)
    await session.commit()

    return UserResponse(id=user.id, email=user.email, role=user.role)


@router.post("/login", response_model=UserResponse)
@limiter.limit("5/minute", key_func=get_remote_address)
async def login(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    payload = LoginRequest.model_validate(await request.json())
    email = payload.email.strip().lower()
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user.last_login_at = datetime.now(UTC)
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        settings=settings,
    )
    _set_auth_cookie(response, token, settings)
    await session.commit()

    return UserResponse(id=user.id, email=user.email, role=user.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> Response:
    _clear_auth_cookie(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, role=user.role)
