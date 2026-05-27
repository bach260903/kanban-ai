"""Unit tests for task WIP helpers and Kanban moves (T068)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError, WIPLimitError
from app.models.diff import Diff, DiffReviewStatus
from app.models.task import Task, TaskStatus
from app.services.diff_service import DiffService
from app.services.kanban_service import KanbanService
from app.services.task_service import TaskService


async def _insert_task(
    session: AsyncSession,
    project_id: UUID,
    *,
    status: TaskStatus,
    title: str,
    priority: int = 0,
) -> Task:
    now = datetime.now(timezone.utc)
    row = Task(
        project_id=project_id,
        title=title,
        description=None,
        status=status,
        priority=priority,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


@pytest_asyncio.fixture
async def project_id(async_db_session: AsyncSession) -> UUID:
    """Unique project per test (avoids clashing ``projects.name`` unique)."""
    from sqlalchemy import text

    res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('__pytest_wip__', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    pid = res.scalar_one()
    await async_db_session.flush()
    return pid


@pytest.mark.asyncio
async def test_count_in_progress_counts_only_in_progress_for_project(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="a")
    await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="b")
    await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="c")
    assert await TaskService.count_in_progress(async_db_session, project_id) == 1


@pytest.mark.asyncio
async def test_move_task_raises_wip_limit_when_in_progress_slot_taken(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    a = await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="wip-a")
    b = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="wip-b")
    with pytest.raises(WIPLimitError, match="WIP limit"):
        await KanbanService.move_task(b.id, TaskStatus.IN_PROGRESS, async_db_session, defer_coder_start=True)
    await async_db_session.refresh(a)
    await async_db_session.refresh(b)
    assert a.status == TaskStatus.IN_PROGRESS
    assert b.status == TaskStatus.TODO


@pytest.mark.asyncio
async def test_move_task_review_to_done_idempotent(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="hil")
    out1 = await KanbanService.move_task(t.id, TaskStatus.DONE, async_db_session, defer_coder_start=True)
    out2 = await KanbanService.move_task(t.id, TaskStatus.DONE, async_db_session, defer_coder_start=True)
    assert out1.id == t.id
    assert out2.id == t.id
    assert out1.status == TaskStatus.DONE
    assert out2.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_second_approve_latest_pending_raises(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    """Approving the same pending diff twice is rejected (latest diff no longer pending)."""
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="diffy")
    diff = Diff(
        task_id=t.id,
        agent_run_id=None,
        content="--- a\n+++ b\n",
        original_content="old",
        modified_content="new",
        files_affected=["x.py"],
        review_status=DiffReviewStatus.PENDING,
    )
    async_db_session.add(diff)
    await async_db_session.flush()

    await DiffService.approve_latest_pending(
        async_db_session, task_id=t.id, project_id=project_id
    )
    with pytest.raises(InvalidTransitionError, match="not pending approval"):
        await DiffService.approve_latest_pending(
            async_db_session, task_id=t.id, project_id=project_id
        )


async def _insert_user(session: AsyncSession, *, email: str, display_name: str) -> UUID:
    user_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO users (id, email, hashed_password, display_name)
            VALUES (:id, :email, 'hash', :display_name)
            """
        ),
        {"id": user_id, "email": email, "display_name": display_name},
    )
    await session.flush()
    return user_id


async def _insert_member(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    role: str = "developer",
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (:project_id, :user_id, :role)
            """
        ),
        {"project_id": project_id, "user_id": user_id, "role": role},
    )
    await session.flush()


@pytest.mark.asyncio
async def test_multi_user_wip_allows_different_developers_in_parallel(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    dev_a = await _insert_user(async_db_session, email="dev-a@wip.test", display_name="Dev A")
    dev_b = await _insert_user(async_db_session, email="dev-b@wip.test", display_name="Dev B")
    await _insert_member(async_db_session, project_id, dev_a)
    await _insert_member(async_db_session, project_id, dev_b)

    task_a = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="task-a")
    task_b = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="task-b")

    await KanbanService.move_task(
        task_a.id,
        TaskStatus.IN_PROGRESS,
        async_db_session,
        current_user_id=dev_a,
        defer_coder_start=True,
    )
    out_b = await KanbanService.move_task(
        task_b.id,
        TaskStatus.IN_PROGRESS,
        async_db_session,
        current_user_id=dev_b,
        defer_coder_start=True,
    )

    assert out_b.status == TaskStatus.IN_PROGRESS
    assert out_b.assigned_to == dev_b


@pytest.mark.asyncio
async def test_multi_user_wip_blocks_second_task_for_same_developer(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    dev_a = await _insert_user(async_db_session, email="dev-a2@wip.test", display_name="Dev A2")
    await _insert_member(async_db_session, project_id, dev_a)

    await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="busy", priority=0)
    task = await async_db_session.execute(
        text("SELECT id FROM tasks WHERE title = 'busy'")
    )
    busy_id = task.scalar_one()
    await async_db_session.execute(
        text("UPDATE tasks SET assigned_to = :uid WHERE id = :tid"),
        {"uid": dev_a, "tid": busy_id},
    )
    todo = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="next")

    with pytest.raises(WIPLimitError, match="per developer"):
        await KanbanService.move_task(
            todo.id,
            TaskStatus.IN_PROGRESS,
            async_db_session,
            current_user_id=dev_a,
            defer_coder_start=True,
        )


@pytest.mark.asyncio
async def test_assignment_conflict_blocks_other_developer(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    dev_a = await _insert_user(async_db_session, email="dev-a3@wip.test", display_name="Dev A3")
    dev_b = await _insert_user(async_db_session, email="dev-b3@wip.test", display_name="Dev B3")
    await _insert_member(async_db_session, project_id, dev_a)
    await _insert_member(async_db_session, project_id, dev_b)

    assigned = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="owned")
    assigned.assigned_to = dev_a
    await async_db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await KanbanService.move_task(
            assigned.id,
            TaskStatus.IN_PROGRESS,
            async_db_session,
            current_user_id=dev_b,
            defer_coder_start=True,
        )
    assert exc.value.status_code == 403
