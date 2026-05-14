"""Intent persistence (US4 / T037)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intent import Intent


class IntentService:
    """Store PO-submitted intent text per project."""

    @staticmethod
    async def create(session: AsyncSession, project_id: UUID, content: str) -> Intent:
        intent = Intent(project_id=project_id, content=content)
        session.add(intent)
        await session.flush()
        return intent

    @staticmethod
    async def list_by_project(session: AsyncSession, project_id: UUID) -> list[Intent]:
        result = await session.execute(
            select(Intent).where(Intent.project_id == project_id).order_by(Intent.created_at.desc())
        )
        return list(result.scalars().all())
