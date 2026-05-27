"""Unit tests for task dependency service (US4 / T063–T065)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import CircularDependencyError, DependencyBlockedError
from app.models.task import Task, TaskStatus
from app.services import dependency_service


async def _insert_task(
    session: AsyncSession,
    project_id: UUID,
    *,
    title: str,
    status: TaskStatus = TaskStatus.TODO,
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
    res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('__pytest_deps__', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    pid = res.scalar_one()
    await async_db_session.flush()
    return pid


@pytest.mark.asyncio
async def test_add_dependency_blocks_until_prerequisite_done(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A")
    task_b = await _insert_task(async_db_session, project_id, title="B")

    await dependency_service.add_dependency(
        async_db_session, task_b.id, task_a.id, project_id
    )
    await async_db_session.refresh(task_b)

    assert task_b.is_blocked is True

    task_a.status = TaskStatus.DONE
    await async_db_session.flush()
    unlocked = await dependency_service.unlock_dependents(async_db_session, task_a.id)
    await async_db_session.refresh(task_b)

    assert task_b.id in unlocked
    assert task_b.is_blocked is False


@pytest.mark.asyncio
async def test_add_dependency_rejects_cycle(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A-cycle")
    task_b = await _insert_task(async_db_session, project_id, title="B-cycle")

    await dependency_service.add_dependency(
        async_db_session, task_b.id, task_a.id, project_id
    )

    with pytest.raises(CircularDependencyError, match="Circular dependency"):
        await dependency_service.add_dependency(
            async_db_session, task_a.id, task_b.id, project_id
        )


@pytest.mark.asyncio
async def test_add_dependency_on_done_prerequisite_clears_blocked_flag(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A-done", status=TaskStatus.DONE)
    task_b = await _insert_task(async_db_session, project_id, title="B-stale")
    task_b.is_blocked = True
    await async_db_session.flush()

    await dependency_service.add_dependency(
        async_db_session, task_b.id, task_a.id, project_id
    )
    await async_db_session.refresh(task_b)

    assert task_b.is_blocked is False


@pytest.mark.asyncio
async def test_unlock_dependents_reblocks_when_other_prerequisite_open(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A-open")
    task_b = await _insert_task(async_db_session, project_id, title="B-open")
    task_c = await _insert_task(async_db_session, project_id, title="C-dep")
    await dependency_service.add_dependency(async_db_session, task_c.id, task_a.id, project_id)
    await dependency_service.add_dependency(async_db_session, task_c.id, task_b.id, project_id)
    await async_db_session.refresh(task_c)
    assert task_c.is_blocked is True

    task_a.status = TaskStatus.DONE
    await async_db_session.flush()
    unlocked = await dependency_service.unlock_dependents(async_db_session, task_a.id)
    await async_db_session.refresh(task_c)

    assert unlocked == []
    assert task_c.is_blocked is True


@pytest.mark.asyncio
async def test_enforce_not_blocked_revalidates_stale_false_flag(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A-enforce")
    task_b = await _insert_task(async_db_session, project_id, title="B-enforce")
    await dependency_service.add_dependency(
        async_db_session, task_b.id, task_a.id, project_id
    )
    task_b.is_blocked = False
    await async_db_session.flush()

    with pytest.raises(DependencyBlockedError, match="blocked"):
        await dependency_service.enforce_not_blocked_for_move(async_db_session, task_b)


@pytest.mark.asyncio
async def test_delete_prerequisite_resyncs_dependent_blocked_flag(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A-del")
    task_b = await _insert_task(async_db_session, project_id, title="B-del")
    await dependency_service.add_dependency(
        async_db_session, task_b.id, task_a.id, project_id
    )
    await async_db_session.refresh(task_b)
    assert task_b.is_blocked is True

    await async_db_session.delete(task_a)
    await async_db_session.flush()
    await async_db_session.refresh(task_b)

    assert task_b.is_blocked is False


@pytest.mark.asyncio
async def test_remove_dependency_recomputes_blocked_flag(
    async_db_session: AsyncSession,
    project_id: UUID,
) -> None:
    task_a = await _insert_task(async_db_session, project_id, title="A-remove")
    task_b = await _insert_task(async_db_session, project_id, title="B-remove")

    await dependency_service.add_dependency(
        async_db_session, task_b.id, task_a.id, project_id
    )
    await dependency_service.remove_dependency(
        async_db_session, task_b.id, task_a.id, project_id=project_id
    )
    await async_db_session.refresh(task_b)

    assert task_b.is_blocked is False
