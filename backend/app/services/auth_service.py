"""Authentication helpers: password hashing, JWT, register/login."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.user import User


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (compatible with existing ``security.py`` hashes)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    user_id: uuid.UUID,
    secret: str,
    algorithm: str,
    expire_days: int,
) -> str:
    """Create a signed JWT for the given user id."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=expire_days)
    payload = {
        "sub": str(user_id),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str) -> uuid.UUID:
    """Decode and validate a JWT; return the user id from ``sub``."""
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing sub")
        return uuid.UUID(str(sub))
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


async def register_user(
    session: AsyncSession,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """Register a new user; raise 409 if email already exists."""
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=email,
        hashed_password=await asyncio.to_thread(hash_password, password),
        display_name=display_name,
    )
    session.add(user)
    await session.flush()
    return user


async def login_user(
    session: AsyncSession,
    email: str,
    password: str,
    settings: Settings,
) -> tuple[User, str]:
    """Authenticate user and return (user, access_token)."""
    user = await session.scalar(select(User).where(User.email == email))
    password_ok = user is not None and await asyncio.to_thread(
        verify_password,
        password,
        user.hashed_password,
    )
    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    user.last_login_at = datetime.now(timezone.utc)
    token = create_access_token(
        user.id,
        settings.jwt_secret_key,
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    return user, token
