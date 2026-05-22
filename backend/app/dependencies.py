"""FastAPI dependencies for auth and project role checks."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.database import get_db
from app.models.project_member import ProjectMember, ProjectRole
from app.models.user import User
from app.services import auth_service

_bearer = HTTPBearer(auto_error=False)


def get_settings() -> Settings:
    """FastAPI dependency returning application settings."""
    return settings


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
) -> User:
    """Require a valid Bearer token and return the authenticated user."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user_id = auth_service.decode_token(
        creds.credentials,
        app_settings.jwt_secret_key,
        app_settings.jwt_algorithm,
    )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
) -> User | None:
    """Return the authenticated user, or None if token is missing or invalid."""
    if creds is None or not creds.credentials:
        return None
    try:
        user_id = auth_service.decode_token(
            creds.credentials,
            app_settings.jwt_secret_key,
            app_settings.jwt_algorithm,
        )
    except HTTPException:
        return None
    return await session.get(User, user_id)


def require_role(*allowed_roles: ProjectRole) -> Any:
    """Factory: Depends() that ensures the user has one of ``allowed_roles`` in the project."""

    async def check(
        project_id: uuid.UUID = Path(...),
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> ProjectMember:
        member = await session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        if member is None or member.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return member

    return Depends(check)


require_owner: Callable[..., Any] = require_role(ProjectRole.OWNER)
require_leader_or_above: Callable[..., Any] = require_role(
    ProjectRole.OWNER,
    ProjectRole.LEADER,
)
require_developer_or_above: Callable[..., Any] = require_role(
    ProjectRole.OWNER,
    ProjectRole.LEADER,
    ProjectRole.DEVELOPER,
)
require_any_member: Callable[..., Any] = require_role(
    ProjectRole.OWNER,
    ProjectRole.LEADER,
    ProjectRole.DEVELOPER,
    ProjectRole.VIEWER,
)
