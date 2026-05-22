"""Development-only JWT issuance (never enable in production)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from jose import jwt

from app.config import settings

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/token")
async def issue_dev_token() -> dict[str, str]:
    """
    Return a short-lived HS256 JWT for local UI testing.

    Enabled only when ``DEV_AUTH_ENABLED=true`` in environment.
    """
    if not settings.dev_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dev auth is disabled.",
        )
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "dev-user", "exp": now + timedelta(days=7)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}
