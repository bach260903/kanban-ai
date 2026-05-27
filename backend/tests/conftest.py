"""Pytest fixtures: async DB, HTTP client, JWT headers, sample project row."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Bootstrap env before importing app (DATABASE_URL / JWT_SECRET from repo .env).
_repo_root = Path(__file__).resolve().parents[2]


def _merge_dotenv() -> None:
    env_path = _repo_root / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_merge_dotenv()
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("DISABLE_WEBHOOK_WORKER", "1")

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def async_db_session() -> Any:
    """Per-test DB session: shared connection + outer transaction rolled back (no commit)."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    # Return pooled asyncpg connections on this loop before pytest closes it.
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client() -> Any:
    """HTTPX async client against the FastAPI ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


@pytest_asyncio.fixture
async def auth_headers() -> AsyncGenerator[dict[str, str], None]:
    """JWT Bearer header for authenticated API tests using a real user id."""
    user_id = uuid.uuid4()
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO users (id, email, hashed_password, display_name)
                VALUES (:id, :email, :hashed_password, :display_name)
                ON CONFLICT (email) DO UPDATE
                SET display_name = EXCLUDED.display_name
                RETURNING id
                """
            ),
            {
                "id": user_id,
                "email": "pytest-auth-user@example.com",
                "hashed_password": "pytest-hash",
                "display_name": "Pytest Auth User",
            },
        )
        user_id = res.scalar_one()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user_id), "exp": now + timedelta(hours=24)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    yield {"Authorization": f"Bearer {token}"}
    await engine.dispose()


@pytest_asyncio.fixture
async def sample_project(async_db_session: AsyncSession) -> UUID:
    """One ``projects`` row (raw SQL until ORM exists in T008)."""
    res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('__pytest_project__', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    row = res.one()
    await async_db_session.flush()
    return row[0]
