"""Kanban tasks API (US7 / T050)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_jwt
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskKanbanItem, TasksGroupedResponse
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

router = APIRouter(prefix="/projects", tags=["tasks"])


def _group_tasks_by_status(tasks: list[Task]) -> TasksGroupedResponse:
    buckets: dict[str, list[TaskKanbanItem]] = {
        TaskStatus.TODO.value: [],
        TaskStatus.IN_PROGRESS.value: [],
        TaskStatus.REVIEW.value: [],
        TaskStatus.DONE.value: [],
        TaskStatus.REJECTED.value: [],
        TaskStatus.CONFLICT.value: [],
    }
    for t in tasks:
        key = t.status.value
        if key not in buckets:
            continue
        buckets[key].append(TaskKanbanItem.model_validate(t))
    return TasksGroupedResponse(
        todo=buckets[TaskStatus.TODO.value],
        in_progress=buckets[TaskStatus.IN_PROGRESS.value],
        review=buckets[TaskStatus.REVIEW.value],
        done=buckets[TaskStatus.DONE.value],
        rejected=buckets[TaskStatus.REJECTED.value],
        conflict=buckets[TaskStatus.CONFLICT.value],
    )


@router.get("/{project_id}/tasks", response_model=TasksGroupedResponse)
async def list_tasks_grouped(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TasksGroupedResponse:
    await ProjectService.get(session, project_id)
    rows = await TaskService.list_by_project(session, project_id)
    return _group_tasks_by_status(rows)
