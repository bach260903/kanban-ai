"""Task branch read API (US15 / T104)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError
from app.middleware.auth import require_jwt
from app.models.task_branch import TaskBranch
from app.schemas.task_branch import TaskBranchResponse
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["branches"])


@router.get("/{task_id}/branch", response_model=TaskBranchResponse)
async def get_task_branch(
    task_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskBranchResponse:
    """Return the ``task_branches`` row for this task (404 if none)."""
    await TaskService.get(session, task_id)
    row = await session.scalar(select(TaskBranch).where(TaskBranch.task_id == task_id))
    if row is None:
        raise NotFoundError("No branch record for this task.")
    return TaskBranchResponse.model_validate(row)
