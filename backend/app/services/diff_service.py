"""Latest diff for a Kanban task (US9 / T062)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diff import Diff
from app.services.task_service import TaskService


class DiffService:
    """Read-only access to ``diffs`` rows scoped by project via owning task."""

    @staticmethod
    async def get_latest_for_task(
        session: AsyncSession,
        *,
        task_id: UUID,
        project_id: UUID,
    ) -> Diff | None:
        await TaskService.get(session, task_id, project_id=project_id)
        result = await session.execute(
            select(Diff)
            .where(Diff.task_id == task_id)
            .order_by(Diff.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
