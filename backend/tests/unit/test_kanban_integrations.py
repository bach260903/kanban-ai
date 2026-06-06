"""Unit tests for Kanban notification/webhook/GitHub hooks (T103–T105)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus
from app.services.kanban_service import KanbanService


@pytest_asyncio.fixture
async def project_id(async_db_session: AsyncSession) -> UUID:
    res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('__pytest_kanban_hooks__', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    return res.scalar_one()


async def _insert_task(
    session: AsyncSession,
    project_id: UUID,
    *,
    status: TaskStatus,
    title: str,
) -> Task:
    row = Task(
        project_id=project_id,
        title=title,
        description=None,
        status=status,
        priority=0,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    return row


@pytest.mark.asyncio
async def test_on_task_needs_review_notifies_and_enqueues(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task = await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="Review me")
    with (
        patch(
            "app.services.kanban_service.notification_service.notify_task_needs_review",
            AsyncMock(),
        ) as notify_mock,
        patch(
            "app.services.kanban_service.webhook_service.enqueue_delivery",
            AsyncMock(),
        ) as enqueue_mock,
    ):
        await KanbanService.on_task_needs_review(async_db_session, task)
    notify_mock.assert_awaited_once_with(async_db_session, task)
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.args[2] == "task.needs_review"


@pytest.mark.asyncio
async def test_move_task_to_review_triggers_hooks(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task = await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="Move review")
    with (
        patch.object(KanbanService, "on_task_needs_review", AsyncMock()) as review_hook,
        patch.object(KanbanService, "on_task_assigned", AsyncMock()),
        patch.object(KanbanService, "_on_task_done", AsyncMock()),
    ):
        await KanbanService.move_task(task.id, TaskStatus.REVIEW, async_db_session)
    review_hook.assert_awaited_once()


@pytest.mark.asyncio
async def test_on_task_done_enqueues_webhook(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task = await _insert_task(async_db_session, project_id, status=TaskStatus.DONE, title="Done task")
    with patch(
        "app.services.kanban_service.webhook_service.enqueue_delivery",
        AsyncMock(),
    ) as enqueue_mock:
        await KanbanService._on_task_done(async_db_session, task)
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.args[2] == "task.done"


@pytest.mark.asyncio
async def test_github_push_pr_bg_creates_pr_when_configured(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    """GitHub push + PR creation fires in the background (_github_push_pr_bg)."""
    from pathlib import Path
    from app.services.kanban_service import _github_push_pr_bg

    task = await _insert_task(async_db_session, project_id, status=TaskStatus.DONE, title="Done task")
    mock_diff = type("Diff", (), {"content": "diff text"})()
    mock_config = type("GH", (), {"enabled": True})()

    with (
        patch("app.services.kanban_service.async_session_maker") as session_maker_mock,
        patch(
            "app.services.kanban_service.github_service.commit_and_push_branch",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.kanban_service.DiffService.get_latest_approved_for_task",
            AsyncMock(return_value=mock_diff),
        ),
        patch(
            "app.services.kanban_service.github_service.create_pull_request",
            AsyncMock(return_value="https://github.com/o/r/pull/1"),
        ) as pr_mock,
    ):
        session_mock = AsyncMock()
        session_mock.scalar = AsyncMock(return_value=mock_config)
        session_mock.get = AsyncMock(return_value=task)
        session_mock.__aenter__ = AsyncMock(return_value=session_mock)
        session_mock.__aexit__ = AsyncMock(return_value=False)
        session_maker_mock.return_value = session_mock

        await _github_push_pr_bg(
            project_id=project_id,
            task_id=task.id,
            branch_name="task/abc12345",
            sandbox=Path("/tmp/fake-sandbox"),
            task_title="Done task",
        )

    pr_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_po_review_notifies_when_entering_review(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    from app.services.review_orchestration_service import ReviewOrchestrationService

    task = await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="Escalate")
    with (
        patch.object(KanbanService, "on_task_needs_review", AsyncMock()) as review_hook,
        patch(
            "app.services.review_orchestration_service.EventPublisher.publish",
            AsyncMock(),
        ),
    ):
        await ReviewOrchestrationService._open_po_review(
            async_db_session,
            task,
            project_id=project_id,
            task_id=task.id,
            reason="test",
        )
    review_hook.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_po_review_skips_notify_when_already_in_review(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    from app.services.review_orchestration_service import ReviewOrchestrationService

    task = await _insert_task(async_db_session, project_id, status=TaskStatus.REVIEW, title="Already")
    with (
        patch.object(KanbanService, "on_task_needs_review", AsyncMock()) as review_hook,
        patch(
            "app.services.review_orchestration_service.EventPublisher.publish",
            AsyncMock(),
        ),
    ):
        await ReviewOrchestrationService._open_po_review(
            async_db_session,
            task,
            project_id=project_id,
            task_id=task.id,
            reason="test",
        )
    review_hook.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_agent_error_notifies_and_enqueues(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task = await _insert_task(async_db_session, project_id, status=TaskStatus.IN_PROGRESS, title="Failed")
    with (
        patch(
            "app.services.kanban_service.notification_service.notify_agent_error",
            AsyncMock(),
        ) as notify_mock,
        patch(
            "app.services.kanban_service.webhook_service.enqueue_delivery",
            AsyncMock(),
        ) as enqueue_mock,
    ):
        await KanbanService.on_agent_error(async_db_session, task)
    notify_mock.assert_awaited_once_with(async_db_session, task)
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.args[2] == "agent.error"
