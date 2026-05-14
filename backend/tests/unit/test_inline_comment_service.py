"""Unit tests for inline comments vs current diff files (T106)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError, NotFoundError
from app.models.diff import Diff, DiffReviewStatus
from app.models.task import Task, TaskStatus
from app.schemas.inline_comment import InlineCommentCreate
from app.services.inline_comment_service import InlineCommentService


async def _insert_task(
    session: AsyncSession,
    project_id: UUID,
    *,
    status: TaskStatus,
    title: str,
) -> Task:
    now = datetime.now(timezone.utc)
    row = Task(
        project_id=project_id,
        title=title,
        description=None,
        status=status,
        priority=0,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


@pytest_asyncio.fixture
async def project_id(async_db_session: AsyncSession) -> UUID:
    from sqlalchemy import text

    name = f"__pytest_inline_{uuid.uuid4().hex[:12]}__"
    res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES (:name, 'test', 'python', '', 'active')
            RETURNING id
            """
        ),
        {"name": name},
    )
    pid = res.scalar_one()
    await async_db_session.flush()
    return pid


@pytest.mark.asyncio
async def test_create_comment_accepts_normalized_matching_path(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="c1")
    diff = Diff(
        task_id=t.id,
        agent_run_id=None,
        content="---",
        original_content="a",
        modified_content="b",
        files_affected=["src/module/foo.py"],
        review_status=DiffReviewStatus.PENDING,
    )
    async_db_session.add(diff)
    await async_db_session.flush()

    body = InlineCommentCreate(
        file_path="./src/module/foo.py",
        line_number=10,
        comment_text="nit: typo",
    )
    row = await InlineCommentService.create_for_task(
        async_db_session, task_id=t.id, body=body
    )
    assert row.diff_id == diff.id
    assert row.file_path == "./src/module/foo.py"
    assert row.line_number == 10


@pytest.mark.asyncio
async def test_create_comment_rejects_path_not_in_files_affected(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="c2")
    diff = Diff(
        task_id=t.id,
        agent_run_id=None,
        content="---",
        original_content="a",
        modified_content="b",
        files_affected=["allowed.py"],
        review_status=DiffReviewStatus.PENDING,
    )
    async_db_session.add(diff)
    await async_db_session.flush()

    body = InlineCommentCreate(
        file_path="other.py",
        line_number=1,
        comment_text="x",
    )
    with pytest.raises(InvalidTransitionError, match="files_affected"):
        await InlineCommentService.create_for_task(async_db_session, task_id=t.id, body=body)


@pytest.mark.asyncio
async def test_create_comment_without_diff_returns_404_domain_error(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="c3")
    body = InlineCommentCreate(file_path="x.py", line_number=1, comment_text="y")
    with pytest.raises(NotFoundError, match="No diff available"):
        await InlineCommentService.create_for_task(async_db_session, task_id=t.id, body=body)


@pytest.mark.asyncio
async def test_list_and_delete_scoped_to_task(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="c4")
    diff = Diff(
        task_id=t.id,
        agent_run_id=None,
        content="---",
        original_content="a",
        modified_content="b",
        files_affected=["a.py"],
        review_status=DiffReviewStatus.PENDING,
    )
    async_db_session.add(diff)
    await async_db_session.flush()

    row = await InlineCommentService.create_for_task(
        async_db_session,
        task_id=t.id,
        body=InlineCommentCreate(file_path="a.py", line_number=2, comment_text="note"),
    )
    listed = await InlineCommentService.list_for_task(async_db_session, task_id=t.id)
    assert len(listed) == 1
    assert listed[0].id == row.id

    await InlineCommentService.delete_for_task(
        async_db_session, task_id=t.id, comment_id=row.id
    )
    listed2 = await InlineCommentService.list_for_task(async_db_session, task_id=t.id)
    assert listed2 == []


@pytest.mark.asyncio
async def test_delete_wrong_comment_id_raises_not_found(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="c5")
    fake_id = uuid.uuid4()
    with pytest.raises(NotFoundError, match="Comment not found"):
        await InlineCommentService.delete_for_task(
            async_db_session, task_id=t.id, comment_id=fake_id
        )
