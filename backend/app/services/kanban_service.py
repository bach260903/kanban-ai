"""Kanban transitions + WIP + coder dispatch (US8 / T056)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import coder_node
from app.exceptions import InvalidTransitionError, WIPLimitError
from app.models.task import Task, TaskStatus
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

_ALLOWED_MOVES: frozenset[tuple[TaskStatus, TaskStatus]] = frozenset(
    {
        (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
        (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW),
        (TaskStatus.IN_PROGRESS, TaskStatus.REJECTED),
        (TaskStatus.IN_PROGRESS, TaskStatus.CONFLICT),
        (TaskStatus.REVIEW, TaskStatus.DONE),
        (TaskStatus.REVIEW, TaskStatus.IN_PROGRESS),
    }
)


async def _run_coder_agent_background(task_id: UUID, project_id: UUID) -> None:
    """Fire-and-forget entry: T058 replaces ``coder_node.run`` body."""
    try:
        await coder_node.run(
            {
                "task_id": task_id,
                "project_id": project_id,
            }
        )
    except Exception:
        logger.exception("Coder agent background task failed task_id=%s", task_id)


def _schedule_coder_agent(task_id: UUID, project_id: UUID) -> None:
    asyncio.create_task(_run_coder_agent_background(task_id, project_id))


class KanbanService:
    """Validates task status transitions, enforces WIP = 1, starts coder on ``in_progress``."""

    @staticmethod
    async def move_task(task_id: UUID, to_status: TaskStatus, session: AsyncSession) -> Task:
        task = await TaskService.get(session, task_id)
        from_status = task.status
        if from_status == to_status:
            return task
        if (from_status, to_status) not in _ALLOWED_MOVES:
            raise InvalidTransitionError(
                f"Cannot move task from {from_status.value} to {to_status.value}."
            )
        if to_status == TaskStatus.IN_PROGRESS:
            if await TaskService.count_in_progress(session, task.project_id) >= 1:
                raise WIPLimitError("WIP limit: only one task may be in progress per project.")
        task.status = to_status
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()
        if to_status == TaskStatus.IN_PROGRESS:
            _schedule_coder_agent(task.id, task.project_id)
        return task
