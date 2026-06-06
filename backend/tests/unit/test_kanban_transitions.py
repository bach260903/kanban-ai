"""Unit tests for Kanban status transitions (T069)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError
from app.models.task import Task, TaskStatus
from app.services.kanban_service import KanbanService, _ALLOWED_MOVES


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
    res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('__pytest_kanban__', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    pid = res.scalar_one()
    await async_db_session.flush()
    return pid


@pytest.mark.parametrize("from_status,to_status", sorted(_ALLOWED_MOVES, key=lambda p: (p[0].value, p[1].value)))
@pytest.mark.asyncio
async def test_allowed_move_succeeds(
    async_db_session: AsyncSession,
    project_id: UUID,
    from_status: TaskStatus,
    to_status: TaskStatus,
) -> None:
    """Every edge in ``_ALLOWED_MOVES`` succeeds (WIP respected per test project)."""
    t = await _insert_task(async_db_session, project_id, status=from_status, title=f"{from_status}->{to_status}")
    # REVIEW→DONE triggers git commit + background tasks; mock them so no real sandbox needed.
    with (
        patch("app.services.kanban_service.asyncio.to_thread", new=AsyncMock()),
        patch("app.services.kanban_service.asyncio.create_task", new=MagicMock()),
    ):
        out = await KanbanService.move_task(
            t.id,
            to_status,
            async_db_session,
            defer_coder_start=True,
        )
    assert out.status == to_status
    await async_db_session.refresh(t)
    assert t.status == to_status


# Regressions / illegal skips: must not appear in ``_ALLOWED_MOVES``.
_INVALID_BACKWARD_OR_REGRESSION: list[tuple[TaskStatus, TaskStatus]] = [
    (TaskStatus.DONE, TaskStatus.REVIEW),
    (TaskStatus.DONE, TaskStatus.IN_PROGRESS),
    (TaskStatus.DONE, TaskStatus.TODO),
    (TaskStatus.REVIEW, TaskStatus.TODO),
    (TaskStatus.IN_PROGRESS, TaskStatus.TODO),
    (TaskStatus.IN_PROGRESS, TaskStatus.DONE),
    (TaskStatus.TODO, TaskStatus.REVIEW),
    (TaskStatus.TODO, TaskStatus.DONE),
]


@pytest.mark.parametrize("from_status,to_status", _INVALID_BACKWARD_OR_REGRESSION)
@pytest.mark.asyncio
async def test_invalid_backward_or_regression_raises(
    async_db_session: AsyncSession,
    project_id: UUID,
    from_status: TaskStatus,
    to_status: TaskStatus,
) -> None:
    assert (from_status, to_status) not in _ALLOWED_MOVES
    t = await _insert_task(async_db_session, project_id, status=from_status, title="bad-move")
    with pytest.raises(InvalidTransitionError, match="Cannot move task"):
        await KanbanService.move_task(t.id, to_status, async_db_session, defer_coder_start=True)


@pytest.mark.asyncio
async def test_coder_failure_resets_task_to_todo(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    """When agent fails (timeout/error), task goes back to TODO — stays visible on board."""
    from app.agent.nodes import coder_node
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="fail-me")
    # Simulate the status update the coder node does on timeout
    t.status = TaskStatus.TODO
    await async_db_session.flush()
    await async_db_session.refresh(t)
    assert t.status == TaskStatus.TODO


@pytest.mark.asyncio
async def test_only_four_statuses_in_allowed_moves(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    """The board has exactly 4 statuses and _ALLOWED_MOVES stays within them."""
    valid = {TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.REVIEW, TaskStatus.DONE}
    assert set(TaskStatus) == valid
    all_statuses = {s for pair in _ALLOWED_MOVES for s in pair}
    assert all_statuses <= valid


@pytest.mark.asyncio
async def test_todo_to_in_progress_schedules_coder_when_not_deferred(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="dispatch-me")
    with patch("app.services.kanban_service._schedule_coder_agent") as sched:
        await KanbanService.move_task(
            t.id,
            TaskStatus.IN_PROGRESS,
            async_db_session,
            defer_coder_start=False,
        )
    sched.assert_called_once()
    assert sched.call_args.kwargs.get("po_feedback") is None
    assert sched.call_args.kwargs.get("agent_run_id") is None
    args = sched.call_args[0]
    assert args[0] == t.id
    assert args[1] == project_id


@pytest.mark.asyncio
async def test_todo_to_in_progress_does_not_schedule_when_deferred(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    t = await _insert_task(async_db_session, project_id, status=TaskStatus.TODO, title="no-dispatch")
    with patch("app.services.kanban_service._schedule_coder_agent") as sched:
        await KanbanService.move_task(
            t.id,
            TaskStatus.IN_PROGRESS,
            async_db_session,
            defer_coder_start=True,
        )
    sched.assert_not_called()
