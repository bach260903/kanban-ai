"""Task pause / resume REST API (US11 / T085; test-facing, mirrors WebSocket PAUSE/RESUME)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_jwt
from app.models.agent_pause_state import AgentPauseState
from app.models.audit_log import AuditLogResult
from app.schemas.pause import PauseResumeResponse, PauseStateResponse, TaskResumeBody
from app.services.audit_service import write_audit
from app.services.pause_service import PauseService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

pause_router = APIRouter(prefix="/projects", tags=["pause"])


@pause_router.post("/{project_id}/tasks/{task_id}/pause", response_model=PauseResumeResponse)
async def pause_task(
    project_id: UUID,
    task_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PauseResumeResponse:
    await ProjectService.get(session, project_id)
    await TaskService.get(session, task_id, project_id=project_id)
    await PauseService.pause(session, task_id)
    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="task_pause",
        action_description="REST pause requested for task.",
        result=AuditLogResult.SUCCESS,
        input_refs=[],
        output_refs=[],
    )
    await session.commit()
    paused = await PauseService.is_paused(task_id)
    return PauseResumeResponse(task_id=task_id, paused=paused)


@pause_router.post("/{project_id}/tasks/{task_id}/resume", response_model=PauseResumeResponse)
async def resume_task(
    project_id: UUID,
    task_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[TaskResumeBody, Body()] = TaskResumeBody(),
) -> PauseResumeResponse:
    await ProjectService.get(session, project_id)
    await TaskService.get(session, task_id, project_id=project_id)
    steer: str | None = None
    if body.steering_instructions is not None:
        steer = body.steering_instructions.strip() or None
    await PauseService.resume(session, task_id, steer)
    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="task_resume",
        action_description="REST resume requested for task.",
        result=AuditLogResult.SUCCESS,
        input_refs=[],
        output_refs=[],
    )
    await session.commit()
    paused = await PauseService.is_paused(task_id)
    return PauseResumeResponse(task_id=task_id, paused=paused)


@pause_router.get("/{project_id}/tasks/{task_id}/pause-state", response_model=PauseStateResponse)
async def get_pause_state(
    project_id: UUID,
    task_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PauseStateResponse:
    await ProjectService.get(session, project_id)
    await TaskService.get(session, task_id, project_id=project_id)
    row = await session.scalar(select(AgentPauseState).where(AgentPauseState.task_id == task_id))
    redis_paused = await PauseService.is_paused(task_id)
    if row is None:
        return PauseStateResponse(
            task_id=task_id,
            is_paused=redis_paused,
            state=None,
            steering_instructions=None,
            agent_run_id=None,
            paused_at=None,
            resumed_at=None,
        )
    return PauseStateResponse(
        task_id=task_id,
        is_paused=redis_paused,
        state=row.state.value,
        steering_instructions=row.steering_instructions,
        agent_run_id=row.agent_run_id,
        paused_at=row.paused_at,
        resumed_at=row.resumed_at,
    )
