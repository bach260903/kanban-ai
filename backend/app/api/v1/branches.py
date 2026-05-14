"""Task branch read API (US15 / T104) + inline comments (US16 / T106)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError
from app.middleware.auth import require_jwt
from app.models.task_branch import TaskBranch
from app.schemas.inline_comment import InlineCommentCreate, InlineCommentResponse
from app.schemas.task_branch import TaskBranchResponse
from app.services.inline_comment_service import InlineCommentService
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


@router.get("/{task_id}/comments", response_model=list[InlineCommentResponse])
async def list_task_comments(
    task_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[InlineCommentResponse]:
    rows = await InlineCommentService.list_for_task(session, task_id=task_id)
    return [InlineCommentResponse.model_validate(r) for r in rows]


@router.post(
    "/{task_id}/comments",
    response_model=InlineCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_comment(
    task_id: UUID,
    body: InlineCommentCreate,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InlineCommentResponse:
    row = await InlineCommentService.create_for_task(session, task_id=task_id, body=body)
    await session.commit()
    await session.refresh(row)
    return InlineCommentResponse.model_validate(row)


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment(
    task_id: UUID,
    comment_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await InlineCommentService.delete_for_task(session, task_id=task_id, comment_id=comment_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
