"""Dashboard and project analytics aggregation (US6 / T082–T083)."""

from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger(__name__)

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
                # ``* 1.0`` forces float division — bigint/bigint in Postgres would
                # truncate (e.g. 3/5 = 0), making the success rate always 0% or 100%.
                (func.count().filter(AgentRun.status == AgentRunStatus.SUCCESS) * 1.0)
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


async def get_ai_project_review(session: AsyncSession, project_id: UUID) -> dict:
    """Generate an AI-written overview for a single project."""
    from langchain_core.messages import HumanMessage

    from app.config import settings
    from app.services.llm import get_chat_model

    # ── Gather task data for this project ────────────────────────
    task_rows = await session.execute(
        select(Task.id, Task.title, Task.status, Task.is_blocked, Task.updated_at)
        .where(Task.project_id == project_id)
        .order_by(Task.status, Task.updated_at.desc())
    )
    tasks = task_rows.all()

    stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    counts: dict[str, int] = {s.value: 0 for s in TaskStatus}
    in_progress_tasks: list[dict] = []
    review_tasks: list[dict] = []
    blocked_tasks: list[dict] = []
    stale_tasks: list[dict] = []

    for task_id, title, status_val, is_blocked, updated_at in tasks:
        s = str(status_val.value if hasattr(status_val, "value") else status_val)
        counts[s] = counts.get(s, 0) + 1
        if s == TaskStatus.IN_PROGRESS:
            in_progress_tasks.append({"id": str(task_id), "title": title})
        if s == TaskStatus.REVIEW:
            review_tasks.append({"id": str(task_id), "title": title})
            if updated_at and updated_at < stale_threshold:
                stale_tasks.append({"id": str(task_id), "title": title})
        if is_blocked:
            blocked_tasks.append({"id": str(task_id), "title": title})

    total = sum(counts.values())

    # ── Build prompt ─────────────────────────────────────────────
    def _task_list(items: list[dict], limit: int = 5) -> str:
        lines = [f"  - {t['title']}" for t in items[:limit]]
        if len(items) > limit:
            lines.append(f"  - ... và {len(items) - limit} task khác")
        return "\n".join(lines) if lines else "  (không có)"

    prompt_text = f"""Bạn là trợ lý quản lý dự án phần mềm. Hãy đưa ra nhận xét tổng quan ngắn gọn (4-6 câu) về tình trạng dự án, những điểm nổi bật, rủi ro và gợi ý ưu tiên tiếp theo.

Dữ liệu dự án hiện tại:
- Tổng tasks: {total}
- Todo: {counts.get('todo', 0)} | Đang làm: {counts.get('in_progress', 0)} | Review: {counts.get('review', 0)} | Done: {counts.get('done', 0)} | Rejected: {counts.get('rejected', 0)}

Tasks đang AI thực hiện ({len(in_progress_tasks)}):
{_task_list(in_progress_tasks)}

Tasks đang chờ review ({len(review_tasks)}):
{_task_list(review_tasks)}

Tasks bị block ({len(blocked_tasks)}):
{_task_list(blocked_tasks)}

Tasks chờ review quá 24h ({len(stale_tasks)}):
{_task_list(stale_tasks)}

Viết bằng tiếng Việt, giọng chuyên nghiệp và thực tế. Đừng liệt kê lại số liệu — hãy đưa ra nhận xét phân tích có giá trị."""

    spec = f"{settings.coder_llm_provider}:{settings.groq_model or 'llama-3.3-70b-versatile'}"
    llm = get_chat_model(spec, temperature=0.3)

    try:
        result = await asyncio.to_thread(llm.invoke, [HumanMessage(content=prompt_text)])
        summary: str = result.content if hasattr(result, "content") else str(result)
        summary = summary.strip()
    except Exception:
        logger.warning("AI project review LLM call failed project_id=%s", project_id, exc_info=True)
        summary = "Không thể tạo nhận xét AI lúc này. Vui lòng thử lại sau."

    return {
        "summary": summary,
        "active_tasks": in_progress_tasks,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
