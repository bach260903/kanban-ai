"""PO inline comments on the current task diff (US16 / T106)."""

from __future__ import annotations

from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError, NotFoundError
from app.models.inline_comment import InlineComment
from app.schemas.inline_comment import InlineCommentCreate
from app.services.diff_service import DiffService
from app.services.task_service import TaskService


def _normalize_repo_relative_path(path: str) -> str:
    raw = path.strip().replace("\\", "/")
    if not raw:
        return ""
    return str(PurePosixPath(raw))


class InlineCommentService:
    """CRUD for ``inline_comments`` scoped by task; ``file_path`` validated against latest diff."""

    @staticmethod
    def _file_path_allowed(file_path: str, files_affected: list[str]) -> bool:
        want = _normalize_repo_relative_path(file_path)
        if not want:
            return False
        allowed = {_normalize_repo_relative_path(f) for f in files_affected}
        return want in allowed

    @staticmethod
    async def list_for_task(session: AsyncSession, *, task_id: UUID) -> list[InlineComment]:
        await TaskService.get(session, task_id)
        result = await session.execute(
            select(InlineComment)
            .where(InlineComment.task_id == task_id)
            .order_by(
                InlineComment.file_path.asc(),
                InlineComment.line_number.asc(),
                InlineComment.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_for_task(
        session: AsyncSession,
        *,
        task_id: UUID,
        body: InlineCommentCreate,
    ) -> InlineComment:
        await TaskService.get(session, task_id)
        diff = await DiffService.get_latest_row_for_task(session, task_id=task_id)
        if diff is None:
            raise NotFoundError("No diff available for this task.")
        if not InlineCommentService._file_path_allowed(body.file_path, list(diff.files_affected or [])):
            raise InvalidTransitionError(
                "file_path must be one of the paths in the current diff's files_affected list.",
            )
        fp = body.file_path.strip()
        row = InlineComment(
            task_id=task_id,
            diff_id=diff.id,
            file_path=fp[:1000],
            line_number=body.line_number,
            comment_text=body.comment_text.strip(),
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def delete_for_task(session: AsyncSession, *, task_id: UUID, comment_id: UUID) -> None:
        await TaskService.get(session, task_id)
        row = await session.get(InlineComment, comment_id)
        if row is None or row.task_id != task_id:
            raise NotFoundError("Comment not found.")
        await session.delete(row)
        await session.flush()
