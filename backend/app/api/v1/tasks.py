"""Kanban tasks API (US7 / T050)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import InvalidTransitionError, NotFoundError
from app.middleware.auth import require_jwt
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.audit_log import AuditLogResult
from app.models.feedback import Feedback, FeedbackReferenceType
from app.models.task import Task, TaskStatus
from app.schemas.task import (
    TaskApproveResponse,
    TaskDiffResponse,
    TaskKanbanItem,
    TaskMoveRequest,
    TaskMoveResult,
    TaskRejectRequest,
    TaskRejectResponse,
    TasksGroupedResponse,
)
from app.services.audit_service import write_audit
from app.services.diff_service import DiffService
from app.services.kanban_service import KanbanService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

router = APIRouter(prefix="/projects", tags=["tasks"])


def _group_tasks_by_status(tasks: list[Task]) -> TasksGroupedResponse:
    buckets: dict[str, list[TaskKanbanItem]] = {
        TaskStatus.TODO.value: [],
        TaskStatus.IN_PROGRESS.value: [],
        TaskStatus.REVIEW.value: [],
        TaskStatus.DONE.value: [],
        TaskStatus.REJECTED.value: [],
        TaskStatus.CONFLICT.value: [],
    }
    for t in tasks:
        key = t.status.value
        if key not in buckets:
            continue
        buckets[key].append(TaskKanbanItem.model_validate(t))
    return TasksGroupedResponse(
        todo=buckets[TaskStatus.TODO.value],
        in_progress=buckets[TaskStatus.IN_PROGRESS.value],
        review=buckets[TaskStatus.REVIEW.value],
        done=buckets[TaskStatus.DONE.value],
        rejected=buckets[TaskStatus.REJECTED.value],
        conflict=buckets[TaskStatus.CONFLICT.value],
    )


@router.get("/{project_id}/tasks", response_model=TasksGroupedResponse)
async def list_tasks_grouped(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TasksGroupedResponse:
    await ProjectService.get(session, project_id)
    rows = await TaskService.list_by_project(session, project_id)
    return _group_tasks_by_status(rows)


_NO_DIFF_DETAIL = "No diff available. Agent may still be running."


@router.get("/{project_id}/tasks/{task_id}/diff", response_model=TaskDiffResponse)
async def get_task_diff(
    project_id: UUID,
    task_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
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
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskApproveResponse:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    if task.status != TaskStatus.REVIEW:
        raise InvalidTransitionError("Task must be in review status to approve the diff.")
    diff = await DiffService.approve_latest_pending(session, task_id=task_id, project_id=project_id)
    await KanbanService.move_task(task_id, TaskStatus.DONE, session)
    await session.refresh(task)
    if task.status == TaskStatus.CONFLICT:
        await write_audit(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="task_diff_approve",
            action_description=f"PO approved diff {diff.id}; merge conflict — task left in conflict.",
            result=AuditLogResult.FAILURE,
            input_refs=[str(diff.id)],
            output_refs=[str(task.id)],
        )
    else:
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
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskRejectResponse:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    if task.status != TaskStatus.REVIEW:
        raise InvalidTransitionError("Task must be in review status to reject the diff.")
    fb_text = body.feedback.strip()
    if not fb_text:
        raise InvalidTransitionError("Feedback must not be empty.")
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
    await KanbanService.move_task(task_id, TaskStatus.IN_PROGRESS, session, defer_coder_start=True)
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
    KanbanService.start_coder_agent(
        task_id,
        project_id,
        po_feedback=fb_text,
        agent_run_id=agent_run.id,
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
    "/{project_id}/tasks/{task_id}/move",
    response_model=TaskMoveResult,
)
async def move_task(
    project_id: UUID,
    task_id: UUID,
    body: TaskMoveRequest,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskMoveResult:
    await ProjectService.get(session, project_id)
    task = await TaskService.get(session, task_id, project_id=project_id)
    from_status = task.status
    await KanbanService.move_task(task_id, body.to, session)
    await session.commit()
    await session.refresh(task)
    return TaskMoveResult(
        task_id=task.id,
        from_status=from_status,
        to_status=task.status,
        agent_run_id=None,
    )
