"""Task persistence and queries (US7 / T049)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.task import Task, TaskStatus


class TaskBulkItem(BaseModel):
    """One row for ``create_bulk`` (PLAN breakdown or future importers)."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    priority: int = 0


class TaskService:
    """CRUD helpers for Kanban ``Task`` rows."""

    @staticmethod
    def _coerce_item(raw: TaskBulkItem | Mapping[str, Any]) -> TaskBulkItem:
        if isinstance(raw, TaskBulkItem):
            return raw
        return TaskBulkItem.model_validate(raw)

    @staticmethod
    async def create_bulk(
        session: AsyncSession,
        project_id: UUID,
        items: Sequence[TaskBulkItem | Mapping[str, Any]],
        *,
        status: TaskStatus = TaskStatus.TODO,
    ) -> list[Task]:
        """Insert many tasks in one flush (e.g. PLAN task breakdown)."""
        created: list[Task] = []
        now = datetime.now(timezone.utc)
        for raw in items:
            row = TaskService._coerce_item(raw)
            title = row.title.strip()[:500]
            if not title:
                continue
            if row.description is None:
                desc = None
            else:
                d = row.description.strip()
                desc = d if d else None
            task = Task(
                project_id=project_id,
                title=title,
                description=desc,
                status=status,
                priority=int(row.priority),
                updated_at=now,
            )
            session.add(task)
            created.append(task)
        if not created:
            raise ValueError("No valid tasks to insert from bulk payload.")
        await session.flush()
        return created

    @staticmethod
    async def list_by_project(session: AsyncSession, project_id: UUID) -> list[Task]:
        """All tasks for a project (flat list; API may group by status)."""
        result = await session.execute(
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.status.asc(), Task.priority.asc(), Task.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, task_id: UUID, *, project_id: UUID | None = None) -> Task:
        task = await session.get(Task, task_id)
        if task is None:
            raise NotFoundError("Task not found.")
        if project_id is not None and task.project_id != project_id:
            raise NotFoundError("Task not found.")
        return task

    @staticmethod
    async def count_in_progress(session: AsyncSession, project_id: UUID) -> int:
        """Count tasks in ``in_progress`` for WIP = 1 enforcement."""
        n = await session.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.project_id == project_id, Task.status == TaskStatus.IN_PROGRESS)
        )
        return int(n or 0)
