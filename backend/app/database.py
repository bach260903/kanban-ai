"""Async SQLAlchemy engine and FastAPI ``get_db`` session dependency."""

from collections.abc import AsyncGenerator

import app.models  # noqa: F401 — register ORM mappers and ``Base.metadata`` tables
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models.base import Base

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield one request-scoped async session; closes when the request finishes."""
    async with async_session_maker() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose connection pool (call from app lifespan on shutdown)."""
    await engine.dispose()


__all__ = [
    "Base",
    "async_session_maker",
    "dispose_engine",
    "engine",
    "get_db",
]
