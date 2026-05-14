"""Pytest fixtures: async DB, HTTP client, JWT headers, sample project row."""

from __future__ import annotations

import os
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

from app.config import settings  # noqa: E402
from app.database import engine, get_db  # noqa: E402
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


@pytest_asyncio.fixture
async def test_client() -> Any:
    """HTTPX async client against the FastAPI ASGI app with ``get_db`` overridden."""

    async def _override_get_db():
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def auth_headers() -> dict[str, str]:
    """JWT Bearer header for authenticated API tests (T017+)."""
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "test-user", "exp": now + timedelta(hours=24)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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
