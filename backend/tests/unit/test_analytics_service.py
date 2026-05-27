"""Unit tests for analytics service (US6 / T082–T083)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.schemas.analytics import AnalyticsResponse, DashboardResponse
from app.services import analytics_service


@pytest_asyncio.fixture
async def seeded_project(async_db_session: AsyncSession) -> dict:
    user_res = await async_db_session.execute(
        text(
            """
            INSERT INTO users (email, hashed_password, display_name)
            VALUES (:email, 'hash', 'Analytics User')
            RETURNING id
            """
        ),
        {"email": f"analytics-{uuid.uuid4().hex[:8]}@example.com"},
    )
    user_id = user_res.scalar_one()

    project_res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES ('Analytics Project', 'test', 'python', '', 'active')
            RETURNING id
            """
        )
    )
    project_id = project_res.scalar_one()

    await async_db_session.execute(
        text(
            """
            INSERT INTO project_members (project_id, user_id, role)
            VALUES (:pid, :uid, 'owner')
            """
        ),
        {"pid": project_id, "uid": user_id},
    )

    stale_at = datetime.now(timezone.utc) - timedelta(hours=30)
    now = datetime.now(timezone.utc)
    for title, status, updated_at in (
        ("Todo task", "todo", now),
        ("Active task", "in_progress", now),
        ("Stale review", "review", stale_at),
        ("Done task", "done", now),
    ):
        await async_db_session.execute(
            text(
                """
                INSERT INTO tasks (project_id, title, description, status, priority, updated_at)
                VALUES (:pid, :title, NULL, :status, 0, :updated_at)
                """
            ),
            {"pid": project_id, "title": title, "status": status, "updated_at": updated_at},
        )

    task_res = await async_db_session.execute(
        text("SELECT id FROM tasks WHERE project_id = :pid AND title = 'Done task'"),
        {"pid": project_id},
    )
    task_id = task_res.scalar_one()

    started = now - timedelta(hours=2)
    completed = now - timedelta(hours=1)
    run = AgentRun(
        project_id=project_id,
        task_id=task_id,
        agent_type=AgentType.CODER,
        agent_version="1.0.0",
        status=AgentRunStatus.SUCCESS,
        input_artifacts=[],
        output_artifacts=[],
        started_at=started,
        completed_at=completed,
    )
    async_db_session.add(run)

    await async_db_session.execute(
        text(
            """
            INSERT INTO audit_logs (
                agent_id, agent_version, action_type, action_description,
                timestamp, input_refs, output_refs, result, project_id, task_id
            )
            VALUES (
                'coder', '1.0.0', 'coder_run_tests', 'failed tests',
                :ts, '{}', '{}', 'failure', :pid, :tid
            )
            """
        ),
        {"ts": now, "pid": project_id, "tid": task_id},
    )

    await async_db_session.execute(
        text(
            """
            INSERT INTO review_reports (task_id, score, status, created_at)
            VALUES (:tid, 80, 'complete', :created_at)
            """
        ),
        {"tid": task_id, "created_at": now},
    )

    await async_db_session.flush()
    return {"user_id": user_id, "project_id": project_id}


@pytest.mark.asyncio
async def test_get_dashboard_data_counts_and_stale(
    async_db_session: AsyncSession,
    seeded_project: dict,
) -> None:
    data = await analytics_service.get_dashboard_data(
        async_db_session,
        seeded_project["user_id"],
    )
    payload = DashboardResponse.model_validate(data)
    assert len(payload.projects) == 1
    project = payload.projects[0]
    assert project.name == "Analytics Project"
    assert project.primary_language == "python"
    assert project.task_counts["todo"] == 1
    assert project.task_counts["in_progress"] == 1
    assert project.task_counts["review"] == 1
    assert project.task_counts["done"] == 1
    assert project.stale_count == 1
    assert project.member_count == 1


@pytest.mark.asyncio
async def test_get_project_analytics_aggregates_metrics(
    async_db_session: AsyncSession,
    seeded_project: dict,
) -> None:
    now = datetime.now(timezone.utc)
    data = await analytics_service.get_project_analytics(
        async_db_session,
        seeded_project["project_id"],
        now - timedelta(days=1),
        now + timedelta(hours=1),
    )
    payload = AnalyticsResponse.model_validate(data)
    assert payload.by_backend
    assert payload.by_backend[0].agent_type == "coder"
    assert payload.by_backend[0].avg_seconds > 0
    assert payload.by_backend[0].first_approve_rate == 1.0
    assert payload.reviewer_avg_score == 80.0
    assert payload.error_breakdown
    assert payload.error_breakdown[0].action_type == "coder_run_tests"
    assert payload.error_breakdown[0].count == 1


@pytest.mark.asyncio
async def test_get_project_analytics_member_metrics_respect_period(
    async_db_session: AsyncSession,
    seeded_project: dict,
) -> None:
    now = datetime.now(timezone.utc)
    in_range = await analytics_service.get_project_analytics(
        async_db_session,
        seeded_project["project_id"],
        now - timedelta(days=1),
        now + timedelta(hours=1),
    )
    assert in_range["by_member"]

    out_of_range = await analytics_service.get_project_analytics(
        async_db_session,
        seeded_project["project_id"],
        now - timedelta(days=30),
        now - timedelta(days=20),
    )
    assert out_of_range["by_member"] == []


@pytest.mark.asyncio
async def test_get_dashboard_data_excludes_archived_projects(
    async_db_session: AsyncSession,
    seeded_project: dict,
) -> None:
    await async_db_session.execute(
        text("UPDATE projects SET status = 'archived' WHERE id = :pid"),
        {"pid": seeded_project["project_id"]},
    )
    await async_db_session.flush()

    data = await analytics_service.get_dashboard_data(
        async_db_session,
        seeded_project["user_id"],
    )
    assert data["projects"] == []
