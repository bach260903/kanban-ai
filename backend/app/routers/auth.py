"""Auth endpoints: register, login, current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await auth_service.register_user(
        session,
        body.email,
        body.password,
        body.display_name,
    )
    token = auth_service.create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    await session.commit()
    await session.refresh(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user, token = await auth_service.login_user(
        session,
        body.email,
        body.password,
        settings,
    )
    await session.commit()
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user)
