"""Kanban tasks API (US7 / T050)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    require_any_member,
    require_developer_or_above,
    require_leader_or_above,
)
from app.exceptions import InvalidTransitionError, NotFoundError
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.audit_log import AuditLogResult
from app.models.feedback import Feedback, FeedbackReferenceType
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task, TaskStatus
from app.schemas.task import (
    AssignRequest,
    TaskApproveResponse,
    TaskCancelResponse,
    TaskCreateRequest,
    TaskDiffResponse,
    TaskKanbanItem,
    TaskMoveRequest,
    TaskMoveResult,
    TaskRejectRequest,
    TaskRejectResponse,
    TaskResponse,
    TasksGroupedResponse,
)
from app.services.audit_service import write_audit
from app.services.diff_service import DiffService
from app.services.inline_comment_service import InlineCommentService
from app.services.kanban_service import KanbanService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

router = APIRouter(prefix="/projects", tags=["tasks"])


def _status_key(status: TaskStatus | str) -> str:
    """Normalize status for grouping (ORM may return ``str`` even when typed as ``TaskStatus``)."""
    return str(status)


def _group_tasks_by_status(tasks: list[Task]) -> TasksGroupedResponse:
    # ``TaskStatus`` is a ``StrEnum``: members are strings (no ``.value`` attribute).
    buckets: dict[str, list[TaskKanbanItem]] = {s: [] for s in TaskStatus}
    for t in tasks:
        key = _status_key(t.status)
        if key not in buckets:
            continue
        buckets[key].append(TaskKanbanItem.model_validate(t))
    return TasksGroupedResponse(
        todo=buckets[TaskStatus.TODO],
        in_progress=buckets[TaskStatus.IN_PROGRESS],
        review=buckets[TaskStatus.REVIEW],
        done=buckets[TaskStatus.DONE],
    )


@router.get("/{project_id}/tasks", response_model=TasksGroupedResponse)
async def list_tasks_grouped(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TasksGroupedResponse:
    await ProjectService.get(session, project_id)
    rows = await TaskService.list_by_project(session, project_id)
    return _group_tasks_by_status(rows)


@router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=201,
)
async def create_task(
    project_id: UUID,
    body: TaskCreateRequest,
    _developer: Annotated[ProjectMember, require_developer_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    await ProjectService.get(session, project_id)
    created = await TaskService.create_bulk(
        session,
        project_id,
        [{"title": body.title, "description": body.description, "priority": body.priority}],
        status=TaskStatus.TODO,
    )
    await session.commit()
    await session.refresh(created[0])
    return TaskResponse.model_validate(created[0])


_NO_DIFF_DETAIL = "No diff available. Agent may still be running."


@router.get("/{project_id}/tasks/{task_id}/diff", response_model=TaskDiffResponse)
async def get_task_diff(
    project_id: UUID,
    task_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskDiffResponse:
    await ProjectService.get(session, project_id)
    diff = await DiffService.get_latest_for_task(session, task_id=task_id, project_id=project_id)
    if diff is None:
        raise NotFoundError(_NO_DIFF_DETAIL)
    return TaskDiffResponse.model_validate(diff)


@router.post(
    "/{project_id}/tasks/{task_id}/approve",
    response_model=TaskApproveResponse,
)
async def approve_task(
    project_id: UUID,
    task_id: UUID,
    leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskApproveResponse:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    if task.status == TaskStatus.DONE:
        # Idempotent: already approved and moved to DONE (e.g. double-click)
        diff = await DiffService.get_latest_for_task(session, task_id=task_id, project_id=project_id)
        if diff is None:
            raise InvalidTransitionError("Task is done but no diff was found.")
        return TaskApproveResponse(
            task_id=task.id,
            status=task.status,
            diff_id=diff.id,
            updated_at=task.updated_at,
        )
    if task.status != TaskStatus.REVIEW:
        raise InvalidTransitionError("Task must be in review status to approve the diff.")
    diff = await DiffService.approve_latest_pending(session, task_id=task_id, project_id=project_id)
    await KanbanService.move_task(
        task_id,
        TaskStatus.DONE,
        session,
        current_user_id=leader.user_id,
    )
    await session.refresh(task)
    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="task_diff_approve",
        action_description=f"PO approved code diff {diff.id}; task moved to done.",
        result=AuditLogResult.SUCCESS,
        input_refs=[str(diff.id)],
        output_refs=[str(task.id)],
    )
    await session.commit()
    await session.refresh(task)
    return TaskApproveResponse(
        task_id=task.id,
        status=task.status,
        diff_id=diff.id,
        updated_at=task.updated_at,
    )


@router.post(
    "/{project_id}/tasks/{task_id}/reject",
    response_model=TaskRejectResponse,
)
async def reject_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskRejectRequest,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskRejectResponse:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    if task.status != TaskStatus.REVIEW:
        raise InvalidTransitionError("Task must be in review status to reject the diff.")
    fb_text = body.feedback.strip()
    if not fb_text:
        raise InvalidTransitionError("Feedback must not be empty.")
    diff_pending = await DiffService.get_latest_for_task(session, task_id=task_id, project_id=project_id)
    inline_for_coder: list[dict[str, str | int]] | None = None
    if body.inline_comments is not None:
        if diff_pending is not None and body.inline_comments:
            files = list(diff_pending.files_affected or [])
            for c in body.inline_comments:
                if not InlineCommentService._file_path_allowed(c.file_path, files):
                    raise InvalidTransitionError(
                        "Each inline_comments file_path must be in the current diff's files_affected list.",
                    )
        if body.inline_comments:
            inline_for_coder = [
                {
                    "file_path": c.file_path.strip(),
                    "line_number": c.line_number,
                    "comment_text": c.comment_text.strip(),
                }
                for c in body.inline_comments
            ]
    elif diff_pending is not None:
        ic_list = await InlineCommentService.list_payload_for_task_diff(
            session, task_id=task_id, diff_id=diff_pending.id
        )
        if ic_list:
            inline_for_coder = ic_list
    await DiffService.reject_latest_pending(session, task_id=task_id, project_id=project_id)
    feedback = Feedback(
        project_id=project_id,
        reference_type=FeedbackReferenceType.TASK,
        reference_id=task_id,
        content=fb_text,
    )
    session.add(feedback)
    agent_run = AgentRun(
        project_id=project_id,
        task_id=task_id,
        agent_type=AgentType.CODER,
        agent_version="1.0.0",
        status=AgentRunStatus.RUNNING,
        input_artifacts=[str(task_id)],
        output_artifacts=[],
    )
    session.add(agent_run)
    await session.flush()
    await KanbanService.move_task(
        task_id,
        TaskStatus.IN_PROGRESS,
        session,
        current_user_id=_leader.user_id,
        defer_coder_start=True,
    )
    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="task_diff_reject",
        action_description=f"PO rejected code diff with feedback {feedback.id}; task moved to in_progress.",
        result=AuditLogResult.SUCCESS,
        input_refs=[str(feedback.id)],
        output_refs=[str(agent_run.id)],
    )
    await session.commit()
    project_for_backend = await ProjectService.get(session, project_id)
    _backend = str(project_for_backend.coding_backend) if project_for_backend else "groq"
    KanbanService.start_coder_agent(
        task_id,
        project_id,
        po_feedback=fb_text,
        agent_run_id=agent_run.id,
        inline_comments=inline_for_coder,
        coding_backend=_backend,
    )
    await session.refresh(task)
    await session.refresh(feedback)
    return TaskRejectResponse(
        task_id=task.id,
        status=task.status,
        feedback_id=feedback.id,
        agent_run_id=agent_run.id,
        updated_at=task.updated_at,
    )


@router.post(
    "/{project_id}/tasks/{task_id}/cancel",
    response_model=TaskCancelResponse,
)
async def cancel_task(
    project_id: UUID,
    task_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskCancelResponse:
    """Cancel an in-progress task: stop coder run and move back to To do."""
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    from_status = task.status
    updated = await KanbanService.cancel_in_progress(session, task_id)
    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="task_cancel",
        action_description="User cancelled in-progress coder task.",
        result=AuditLogResult.SUCCESS,
        input_refs=[str(task_id)],
        output_refs=[str(updated.id), str(updated.status)],
    )
    await session.commit()
    await session.refresh(updated)
    return TaskCancelResponse(
        task_id=updated.id,
        from_status=from_status,
        to_status=updated.status,
    )


@router.post(
    "/{project_id}/tasks/{task_id}/move",
    response_model=TaskMoveResult,
)
async def move_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskMoveRequest,
    _developer: Annotated[ProjectMember, require_developer_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskMoveResult:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    from_status = task.status

    # Pre-create AgentRun so agent_run_id is available in the response immediately.
    # Coder is deferred until after commit to avoid running against an uncommitted task state.
    # Only on a REAL transition into in_progress — a no-op move (already in_progress)
    # must not spawn a second coder on the shared sandbox (causes git lock contention).
    pre_created_run: AgentRun | None = None
    if body.to == TaskStatus.IN_PROGRESS and from_status != TaskStatus.IN_PROGRESS:
        pre_created_run = AgentRun(
            project_id=project_id,
            task_id=task_id,
            agent_type=AgentType.CODER,
            agent_version="1.0.0",
            status=AgentRunStatus.RUNNING,
            input_artifacts=[str(task_id)],
            output_artifacts=[],
        )
        session.add(pre_created_run)
        await session.flush()

    await KanbanService.move_task(
        task_id,
        body.to,
        session,
        current_user_id=_developer.user_id,
        agent_run_id=pre_created_run.id if pre_created_run else None,
        defer_coder_start=pre_created_run is not None,
    )
    await session.commit()
    await session.refresh(task)

    if pre_created_run is not None:
        _project = await session.get(Project, project_id)
        _backend = str(_project.coding_backend) if _project else "groq"
        KanbanService.start_coder_agent(task_id, project_id, agent_run_id=pre_created_run.id, coding_backend=_backend)

    return TaskMoveResult(
        task_id=task.id,
        from_status=from_status,
        to_status=task.status,
        agent_run_id=pre_created_run.id if pre_created_run else None,
    )


@router.patch(
    "/{project_id}/tasks/{task_id}/assign",
    response_model=TaskResponse,
)
async def assign_task(
    project_id: UUID,
    task_id: UUID,
    body: AssignRequest,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    if body.user_id is not None:
        target_member = await session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == body.user_id,
            )
        )
        if target_member is None:
            raise NotFoundError("User is not a member of this project.")
    previous_assignee = task.assigned_to
    task.assigned_to = body.user_id
    task.updated_at = datetime.now(timezone.utc)
    if body.user_id is not None and body.user_id != previous_assignee:
        await KanbanService.on_task_assigned(session, task, body.user_id)
    await session.commit()
    await session.refresh(task)
    return TaskResponse.model_validate(task)
