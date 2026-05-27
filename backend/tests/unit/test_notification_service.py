"""Unit tests for notification service (US7 / T090–T091)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.notification import NotificationType
from app.models.task import Task, TaskStatus
from app.services import notification_service


@pytest_asyncio.fixture
async def seeded_task(async_db_session: AsyncSession) -> dict:
    owner_id = uuid.uuid4()
    leader_id = uuid.uuid4()
    assignee_id = uuid.uuid4()
    for uid, email, name in (
        (owner_id, f"owner-{uuid.uuid4().hex[:8]}@example.com", "Owner"),
        (leader_id, f"leader-{uuid.uuid4().hex[:8]}@example.com", "Leader"),
        (assignee_id, f"assignee-{uuid.uuid4().hex[:8]}@example.com", "Assignee"),
    ):
        await async_db_session.execute(
            text(
                """
                INSERT INTO users (id, email, hashed_password, display_name)
                VALUES (:id, :email, 'hash', :name)
                """
            ),
            {"id": uid, "email": email, "name": name},
        )

    project_res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('Notify Project', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    project_id = project_res.scalar_one()

    for uid, role in (
        (owner_id, "owner"),
        (leader_id, "leader"),
        (assignee_id, "developer"),
    ):
        await async_db_session.execute(
            text(
                """
                INSERT INTO project_members (project_id, user_id, role)
                VALUES (:pid, :uid, :role)
                """
            ),
            {"pid": project_id, "uid": uid, "role": role},
        )

    task = Task(
        project_id=project_id,
        title="Notify me",
        description=None,
        status=TaskStatus.TODO,
        priority=0,
        assigned_to=assignee_id,
    )
    async_db_session.add(task)
    await async_db_session.flush()

    return {
        "owner_id": owner_id,
        "leader_id": leader_id,
        "assignee_id": assignee_id,
        "project_id": project_id,
        "task": task,
    }


@pytest.mark.asyncio
async def test_notify_task_assigned_creates_notification(
    async_db_session: AsyncSession,
    seeded_task: dict,
) -> None:
    await notification_service.notify_task_assigned(
        async_db_session,
        seeded_task["task"],
        seeded_task["assignee_id"],
    )
    total, items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["assignee_id"],
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].notification_type == NotificationType.TASK_ASSIGNED
    assert "Notify me" in items[0].content


@pytest.mark.asyncio
async def test_notify_task_needs_review_notifies_leaders_only(
    async_db_session: AsyncSession,
    seeded_task: dict,
) -> None:
    await notification_service.notify_task_needs_review(
        async_db_session,
        seeded_task["task"],
    )
    owner_total, owner_items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["owner_id"],
    )
    leader_total, leader_items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["leader_id"],
    )
    assignee_total, _ = await notification_service.get_notifications(
        async_db_session,
        seeded_task["assignee_id"],
    )
    assert owner_total == 1
    assert leader_total == 1
    assert assignee_total == 0
    assert owner_items[0].notification_type == NotificationType.TASK_NEEDS_REVIEW
    assert leader_items[0].notification_type == NotificationType.TASK_NEEDS_REVIEW


@pytest.mark.asyncio
async def test_notify_agent_error_notifies_leaders_only(
    async_db_session: AsyncSession,
    seeded_task: dict,
) -> None:
    await notification_service.notify_agent_error(
        async_db_session,
        seeded_task["task"],
    )
    owner_total, owner_items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["owner_id"],
    )
    leader_total, leader_items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["leader_id"],
    )
    assignee_total, _ = await notification_service.get_notifications(
        async_db_session,
        seeded_task["assignee_id"],
    )
    assert owner_total == 1
    assert leader_total == 1
    assert assignee_total == 0
    assert owner_items[0].notification_type == NotificationType.AGENT_ERROR
    assert leader_items[0].notification_type == NotificationType.AGENT_ERROR


@pytest.mark.asyncio
async def test_mark_read_not_found_raises(
    async_db_session: AsyncSession,
    seeded_task: dict,
) -> None:
    with pytest.raises(NotFoundError, match="Notification not found"):
        await notification_service.mark_read(
            async_db_session,
            uuid.uuid4(),
            seeded_task["assignee_id"],
        )


@pytest.mark.asyncio
async def test_mark_read_and_mark_all_read(
    async_db_session: AsyncSession,
    seeded_task: dict,
) -> None:
    await notification_service.notify_task_assigned(
        async_db_session,
        seeded_task["task"],
        seeded_task["assignee_id"],
    )
    await notification_service.notify_task_unblocked(
        async_db_session,
        seeded_task["task"],
        seeded_task["assignee_id"],
    )
    total, items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["assignee_id"],
    )
    assert total == 2
    await notification_service.mark_read(
        async_db_session,
        items[0].id,
        seeded_task["assignee_id"],
    )
    total_after_one, unread_items = await notification_service.get_notifications(
        async_db_session,
        seeded_task["assignee_id"],
        unread_only=True,
    )
    assert total_after_one == 1
    assert len(unread_items) == 1

    marked = await notification_service.mark_all_read(
        async_db_session,
        seeded_task["assignee_id"],
    )
    assert marked == 1
    total_after_all, unread_after_all = await notification_service.get_notifications(
        async_db_session,
        seeded_task["assignee_id"],
        unread_only=True,
    )
    assert total_after_all == 0
    assert unread_after_all == []
