"""Auto-dispatch highest-priority todo → in_progress + coder (Phases A & B)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.task import TaskStatus
from app.services.kanban_service import KanbanService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    task_id: UUID
    agent_run_id: UUID
    title: str


class TaskDispatchService:
    """Pick next ``todo`` by ``priority ASC, created_at ASC`` and start the coder."""

    @staticmethod
    async def can_dispatch(session: AsyncSession, project_id: UUID) -> bool:
        project = await ProjectService.get(session, project_id)
        if not project.auto_dispatch_enabled:
            return False
        if await TaskService.count_in_progress(session, project_id) >= 1:
            return False
        if await TaskService.count_by_status(session, project_id, TaskStatus.REVIEW) >= 1:
            return False
        return await TaskService.pick_next_todo(session, project_id) is not None

    @staticmethod
    async def dispatch_next(
        session: AsyncSession,
        project_id: UUID,
        *,
        force: bool = False,
    ) -> DispatchResult | None:
        """Start the next todo task. When ``force`` is False, respects ``auto_dispatch_enabled``."""
        project = await ProjectService.get(session, project_id)
        if not force and not project.auto_dispatch_enabled:
            return None
        if await TaskService.count_in_progress(session, project_id) >= 1:
            return None
        if await TaskService.count_by_status(session, project_id, TaskStatus.REVIEW) >= 1:
            return None

        task = await TaskService.pick_next_todo(session, project_id)
        if task is None:
            return None

        agent_run = AgentRun(
            project_id=project_id,
            task_id=task.id,
            agent_type=AgentType.CODER,
            agent_version="1.0.0",
            status=AgentRunStatus.RUNNING,
            input_artifacts=[str(task.id)],
            output_artifacts=[],
        )
        session.add(agent_run)
        await session.flush()

        await KanbanService.move_task(
            task.id,
            TaskStatus.IN_PROGRESS,
            session,
            defer_coder_start=True,
            agent_run_id=agent_run.id,
        )
        await session.refresh(task)
        return DispatchResult(task_id=task.id, agent_run_id=agent_run.id, title=task.title)

    @staticmethod
    def schedule_dispatch_next(project_id: UUID, *, force: bool = False) -> None:
        """Fire-and-forget after HTTP commit (breakdown done, PO approved, manual dispatch)."""
        asyncio.create_task(_dispatch_background(project_id, force=force))

    @staticmethod
    async def maybe_auto_dispatch(session: AsyncSession, project_id: UUID) -> DispatchResult | None:
        """Dispatch in the current session if policy allows (no background task)."""
        if not await TaskDispatchService.can_dispatch(session, project_id):
            return None
        return await TaskDispatchService.dispatch_next(session, project_id)


async def _dispatch_background(project_id: UUID, *, force: bool = False) -> None:
    async with async_session_maker() as session:
        try:
            result = await TaskDispatchService.dispatch_next(session, project_id, force=force)
            if result is None:
                await session.rollback()
                return
            await session.commit()
            KanbanService.start_coder_agent(
                result.task_id,
                project_id,
                agent_run_id=result.agent_run_id,
            )
            logger.info(
                "Auto-dispatched task_id=%s agent_run_id=%s project_id=%s",
                result.task_id,
                result.agent_run_id,
                project_id,
            )
        except Exception:
            logger.exception("Auto-dispatch failed project_id=%s", project_id)
            await session.rollback()
