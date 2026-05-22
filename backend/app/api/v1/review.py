"""AI review report API — GET /tasks/{task_id}/review (US1 / T033)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import require_jwt
from app.models.review_report import ReviewReport
from app.schemas.review import ReviewReportResponse

router = APIRouter(prefix="/tasks", tags=["review"])


@router.get(
    "/{task_id}/review",
    response_model=ReviewReportResponse,
    summary="Get latest AI review report for a task",
)
async def get_task_review(
    task_id: UUID,
    _: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewReportResponse:
    """Return the most recent ``ReviewReport`` for *task_id*.

    - **200**: Report found — returns full report with inline comments.
    - **404**: No review report exists yet for this task.
    """
    result = await session.execute(
        select(ReviewReport)
        .where(ReviewReport.task_id == task_id)
        .options(selectinload(ReviewReport.comments))
        .order_by(ReviewReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No review report found for task {task_id}.",
        )

    return ReviewReportResponse.model_validate(report)
