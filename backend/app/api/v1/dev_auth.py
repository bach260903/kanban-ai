"""Development-only JWT issuance (never enable in production)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services import auth_service

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/token")
async def issue_dev_token(session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """
    Return a short-lived HS256 JWT for local UI testing.

    Enabled only when ``DEV_AUTH_ENABLED=true`` in environment.
    """
    if not settings.dev_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dev auth is disabled.",
        )
    user = await session.scalar(select(User).where(User.email == "dev@example.local"))
    if user is None:
        user = User(
            email="dev@example.local",
            hashed_password=auth_service.hash_password("dev-password"),
            display_name="Dev User",
        )
        session.add(user)
        await session.flush()
    token = auth_service.create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    await session.commit()
    return {"access_token": token, "token_type": "bearer"}
