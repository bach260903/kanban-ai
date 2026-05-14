"""Latest diff for a Kanban task (US9 / T062–T064)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError
from app.models.diff import Diff, DiffReviewStatus
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

    @staticmethod
    async def get_latest_row_for_task(session: AsyncSession, *, task_id: UUID) -> Diff | None:
        """Latest diff for ``task_id`` (no project check). Caller must enforce access (e.g. JWT + task exists)."""
        result = await session.execute(
            select(Diff)
            .where(Diff.task_id == task_id)
            .order_by(Diff.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_latest_approved_for_task(
        session: AsyncSession,
        *,
        task_id: UUID,
        project_id: UUID,
    ) -> Diff | None:
        """Latest diff in ``approved`` state for the task (e.g. after PO approve, T093)."""
        await TaskService.get(session, task_id, project_id=project_id)
        result = await session.execute(
            select(Diff)
            .where(
                Diff.task_id == task_id,
                Diff.review_status == DiffReviewStatus.APPROVED,
            )
            .order_by(Diff.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def approve_latest_pending(
        session: AsyncSession,
        *,
        task_id: UUID,
        project_id: UUID,
    ) -> Diff:
        """Mark the latest diff as approved (must be ``pending``). Task project scope enforced."""
        diff = await DiffService.get_latest_for_task(session, task_id=task_id, project_id=project_id)
        if diff is None:
            raise InvalidTransitionError("No diff available to approve.")
        if diff.review_status != DiffReviewStatus.PENDING:
            raise InvalidTransitionError("Latest diff is not pending approval.")
        diff.review_status = DiffReviewStatus.APPROVED
        await session.flush()
        return diff

    @staticmethod
    async def reject_latest_pending(
        session: AsyncSession,
        *,
        task_id: UUID,
        project_id: UUID,
    ) -> Diff:
        """Mark the latest diff as rejected (must be ``pending``). Task project scope enforced."""
        diff = await DiffService.get_latest_for_task(session, task_id=task_id, project_id=project_id)
        if diff is None:
            raise InvalidTransitionError("No diff available to reject.")
        if diff.review_status != DiffReviewStatus.PENDING:
            raise InvalidTransitionError("Latest diff is not pending review.")
        diff.review_status = DiffReviewStatus.REJECTED
        await session.flush()
        return diff
