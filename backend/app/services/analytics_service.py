"""Dashboard and project analytics aggregation (US6 / T082–T083)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.audit_log import AuditLog, AuditLogResult
from app.models.project import Project, ProjectStatus
from app.models.project_member import ProjectMember
from app.models.review_report import ReviewReport, ReviewStatus
from app.models.task import Task, TaskStatus
from app.models.user import User

_TASK_STATUSES = (
    TaskStatus.TODO,
    TaskStatus.IN_PROGRESS,
    TaskStatus.REVIEW,
    TaskStatus.DONE,
    TaskStatus.REJECTED,
    TaskStatus.CONFLICT,
)


def _empty_task_counts() -> dict[str, int]:
    return {status.value: 0 for status in _TASK_STATUSES}


async def get_dashboard_data(session: AsyncSession, user_id: UUID) -> dict:
    """Aggregate per-project task counts, stale review tasks, and member counts."""
    projects = list(
        (
            await session.scalars(
                select(Project)
                .join(ProjectMember, ProjectMember.project_id == Project.id)
                .where(
                    ProjectMember.user_id == user_id,
                    Project.status == ProjectStatus.ACTIVE,
                )
                .order_by(Project.name)
            )
        ).all()
    )
    if not projects:
        return {"projects": []}

    project_ids = [project.id for project in projects]
    stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    counts_rows = await session.execute(
        select(Task.project_id, Task.status, func.count())
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id, Task.status)
    )
    counts_by_project: dict[UUID, dict[str, int]] = {
        pid: _empty_task_counts() for pid in project_ids
    }
    for project_id, status, count in counts_rows.all():
        key = str(status.value if hasattr(status, "value") else status)
        counts_by_project[project_id][key] = int(count)

    stale_rows = await session.execute(
        select(Task.project_id, func.count())
        .where(
            Task.project_id.in_(project_ids),
            Task.status == TaskStatus.REVIEW,
            Task.updated_at < stale_threshold,
        )
        .group_by(Task.project_id)
    )
    stale_by_project = {row[0]: int(row[1]) for row in stale_rows.all()}

    member_rows = await session.execute(
        select(ProjectMember.project_id, func.count())
        .where(ProjectMember.project_id.in_(project_ids))
        .group_by(ProjectMember.project_id)
    )
    members_by_project = {row[0]: int(row[1]) for row in member_rows.all()}

    return {
        "projects": [
            {
                "id": project.id,
                "name": project.name,
                "primary_language": project.primary_language,
                "task_counts": counts_by_project.get(project.id, _empty_task_counts()),
                "stale_count": stale_by_project.get(project.id, 0),
                "member_count": members_by_project.get(project.id, 0),
            }
            for project in projects
        ]
    }


async def get_project_analytics(
    session: AsyncSession,
    project_id: UUID,
    from_dt: datetime,
    to_dt: datetime,
) -> dict:
    """Aggregate agent, member, reviewer, and audit metrics for a project."""
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=timezone.utc)
    if to_dt.tzinfo is None:
        to_dt = to_dt.replace(tzinfo=timezone.utc)

    duration_seconds = func.extract(
        "epoch",
        AgentRun.completed_at - AgentRun.started_at,
    )
    backend_rows = await session.execute(
        select(
            AgentRun.agent_type,
            func.avg(
                case(
                    (AgentRun.completed_at.isnot(None), duration_seconds),
                    else_=None,
                )
            ).label("avg_seconds"),
            (
                func.count().filter(AgentRun.status == AgentRunStatus.SUCCESS)
                / func.nullif(func.count(), 0)
            ).label("first_approve_rate"),
            func.count()
            .filter(AgentRun.status == AgentRunStatus.FAILURE)
            .label("error_count"),
        )
        .where(
            AgentRun.project_id == project_id,
            AgentRun.started_at >= from_dt,
            AgentRun.started_at <= to_dt,
        )
        .group_by(AgentRun.agent_type)
        .order_by(AgentRun.agent_type)
    )

    member_rows = await session.execute(
        select(
            func.coalesce(User.display_name, "Unassigned").label("display_name"),
            func.count(Task.id)
            .filter(Task.status == TaskStatus.DONE)
            .label("tasks_done"),
            func.count(Task.id)
            .filter(Task.status == TaskStatus.IN_PROGRESS)
            .label("tasks_in_progress"),
        )
        .select_from(Task)
        .outerjoin(User, Task.assigned_to == User.id)
        .where(
            Task.project_id == project_id,
            Task.updated_at >= from_dt,
            Task.updated_at <= to_dt,
        )
        .group_by(User.id, User.display_name)
        .order_by(func.coalesce(User.display_name, "Unassigned"))
    )

    avg_score = await session.scalar(
        select(func.avg(ReviewReport.score))
        .select_from(ReviewReport)
        .join(Task, Task.id == ReviewReport.task_id)
        .where(
            Task.project_id == project_id,
            ReviewReport.status == ReviewStatus.COMPLETE,
            ReviewReport.created_at >= from_dt,
            ReviewReport.created_at <= to_dt,
            ReviewReport.score.isnot(None),
        )
    )

    error_rows = await session.execute(
        select(AuditLog.action_type, func.count())
        .where(
            AuditLog.project_id == project_id,
            AuditLog.result == AuditLogResult.FAILURE,
            AuditLog.timestamp >= from_dt,
            AuditLog.timestamp <= to_dt,
        )
        .group_by(AuditLog.action_type)
        .order_by(func.count().desc())
    )

    return {
        "period": f"{from_dt.isoformat()}..{to_dt.isoformat()}",
        "by_backend": [
            {
                "agent_type": (
                    row.agent_type.value
                    if hasattr(row.agent_type, "value")
                    else str(row.agent_type)
                ),
                "avg_seconds": float(row.avg_seconds or 0.0),
                "first_approve_rate": float(row.first_approve_rate or 0.0),
                "error_count": int(row.error_count or 0),
            }
            for row in backend_rows.all()
        ],
        "by_member": [
            {
                "display_name": row.display_name,
                "tasks_done": int(row.tasks_done or 0),
                "tasks_in_progress": int(row.tasks_in_progress or 0),
            }
            for row in member_rows.all()
        ],
        "reviewer_avg_score": float(avg_score) if avg_score is not None else None,
        "error_breakdown": [
            {"action_type": action_type, "count": int(count)}
            for action_type, count in error_rows.all()
        ],
    }
