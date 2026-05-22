"""Kanban transitions + WIP + coder dispatch (US8 / T056)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from git.exc import GitCommandError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import route_coder
from app.agent.nodes import cli_coder_node, coder_node, reviewer_node
from app.config import settings
from app.database import async_session_maker
from app.exceptions import InvalidTransitionError, NotFoundError, SandboxEscapeError, WIPLimitError
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.git.branch_service import BranchService
from app.git.git_service import GitService
from app.services.diff_service import DiffService
from app.services.memory_service import MemoryService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


def _sandbox_project_root(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


_ALLOWED_MOVES: frozenset[tuple[TaskStatus, TaskStatus]] = frozenset(
    {
        (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
        (TaskStatus.IN_PROGRESS, TaskStatus.REVIEW),
        (TaskStatus.IN_PROGRESS, TaskStatus.REJECTED),
        (TaskStatus.IN_PROGRESS, TaskStatus.CONFLICT),
        (TaskStatus.REVIEW, TaskStatus.DONE),
        (TaskStatus.REVIEW, TaskStatus.IN_PROGRESS),
    }
)


async def _mark_agent_run_failed(task_id: UUID, agent_run_id: UUID | None) -> None:
    """Mark a stuck RUNNING agent run as failure so the UI can stop polling."""
    try:
        async with async_session_maker() as session:
            run: AgentRun | None = None
            if agent_run_id is not None:
                run = await session.get(AgentRun, agent_run_id)
            if run is None:
                result = await session.execute(
                    select(AgentRun)
                    .where(
                        AgentRun.task_id == task_id,
                        AgentRun.status == AgentRunStatus.RUNNING,
                    )
                    .order_by(AgentRun.started_at.desc())
                    .limit(1)
                )
                run = result.scalar_one_or_none()
            if run is not None and run.status == AgentRunStatus.RUNNING:
                run.status = AgentRunStatus.FAILURE
                run.completed_at = datetime.now(timezone.utc)
                run.result = {"error": "Coder background task failed"}
            task = await session.get(Task, task_id)
            if task is not None and task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.REJECTED
                task.updated_at = datetime.now(timezone.utc)
            await session.commit()
    except Exception:
        logger.exception("Failed to mark agent run failure for task_id=%s", task_id)


async def _run_coder_agent_background(
    task_id: UUID,
    project_id: UUID,
    *,
    po_feedback: str | None = None,
    agent_run_id: UUID | None = None,
    inline_comments: list[dict[str, str | int]] | None = None,
    coding_backend: str = "groq",
) -> None:
    """Fire-and-forget entry for coder agent dispatch."""
    try:
        payload: dict[str, Any] = {
            "task_id": task_id,
            "project_id": project_id,
            "coding_backend": coding_backend,
        }
        if po_feedback:
            payload["po_feedback"] = po_feedback
        if agent_run_id is not None:
            payload["agent_run_id"] = agent_run_id
        if inline_comments:
            payload["inline_comments"] = inline_comments
        node_name = route_coder(payload)
        if node_name == "cli_coder_node":
            state = await cli_coder_node.run(payload)
        else:
            state = await coder_node.run(payload)
        # Run reviewer automatically after coder (plan.md F-003)
        await reviewer_node.run(state)
    except Exception:
        logger.exception("Coder agent background task failed task_id=%s", task_id)
        async with async_session_maker() as session:
            task = await session.get(Task, task_id)
            if task is not None and task.status == TaskStatus.IN_PROGRESS:
                await _mark_agent_run_failed(task_id, agent_run_id)
            else:
                await session.commit()


def _schedule_coder_agent(
    task_id: UUID,
    project_id: UUID,
    *,
    po_feedback: str | None = None,
    agent_run_id: UUID | None = None,
    inline_comments: list[dict[str, str | int]] | None = None,
    coding_backend: str = "groq",
) -> None:
    asyncio.create_task(
        _run_coder_agent_background(
            task_id,
            project_id,
            po_feedback=po_feedback,
            agent_run_id=agent_run_id,
            inline_comments=inline_comments,
            coding_backend=coding_backend,
        )
    )


class KanbanService:
    """Validates task status transitions, enforces WIP = 1, starts coder on ``in_progress``."""

    @staticmethod
    async def cancel_in_progress(session: AsyncSession, task_id: UUID) -> Task:
        """Stop an in-progress coder run and return the task to To do (PO cancel)."""
        task = await TaskService.get(session, task_id)
        if task.status != TaskStatus.IN_PROGRESS:
            raise InvalidTransitionError("Only in-progress tasks can be cancelled.")

        result = await session.execute(
            select(AgentRun)
            .where(
                AgentRun.task_id == task_id,
                AgentRun.status == AgentRunStatus.RUNNING,
            )
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if run is not None:
            run.status = AgentRunStatus.FAILURE
            run.completed_at = datetime.now(timezone.utc)
            run.result = {"error": "Cancelled by user", "code": "USER_CANCELLED"}

        task.status = TaskStatus.TODO
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return task

    @staticmethod
    async def move_task(
        task_id: UUID,
        to_status: TaskStatus,
        session: AsyncSession,
        *,
        po_feedback: str | None = None,
        agent_run_id: UUID | None = None,
        defer_coder_start: bool = False,
    ) -> Task:
        task = await TaskService.get(session, task_id)
        from_status = task.status
        if from_status == to_status:
            return task
        if (from_status, to_status) not in _ALLOWED_MOVES:
            raise InvalidTransitionError(
                f"Cannot move task from {from_status.value} to {to_status.value}."
            )
        if to_status == TaskStatus.IN_PROGRESS:
            if await TaskService.count_in_progress(session, task.project_id) >= 1:
                raise WIPLimitError("WIP limit: only one task may be in progress per project.")

        if from_status == TaskStatus.REVIEW and to_status == TaskStatus.DONE:
            sandbox = _sandbox_project_root(task.project_id)
            try:
                await BranchService.squash_and_merge(session, task.id, sandbox)
            except GitCommandError:
                await session.refresh(task)
                return task
            except NotFoundError:
                logger.info("squash merge skipped: no task branch for task_id=%s", task.id)

        task.status = to_status
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()

        if to_status == TaskStatus.IN_PROGRESS and from_status == TaskStatus.TODO:
            sandbox = _sandbox_project_root(task.project_id)
            await asyncio.to_thread(GitService.init_repo, sandbox)
            await asyncio.to_thread(GitService.configure_identity, sandbox)
            await asyncio.to_thread(GitService.ensure_baseline_commit, sandbox)
            await BranchService.create_task_branch(session, task.id, sandbox)
        if to_status == TaskStatus.DONE and from_status == TaskStatus.REVIEW:
            diff = await DiffService.get_latest_approved_for_task(
                session, task_id=task.id, project_id=task.project_id
            )
            if diff is not None:
                try:
                    await MemoryService.create_entry(session, task.project_id, task.id, diff)
                except Exception:
                    logger.exception("MemoryService.create_entry failed task_id=%s", task.id)
                try:
                    await MemoryService.export_memory_file(session, task.project_id)
                except Exception:
                    logger.exception("MemoryService.export_memory_file failed project_id=%s", task.project_id)
            else:
                logger.info(
                    "Skipping memory write: no approved diff for task_id=%s when moving to done",
                    task.id,
                )
        if to_status == TaskStatus.IN_PROGRESS and not defer_coder_start:
            project = await session.get(Project, task.project_id)
            backend = str(project.coding_backend) if project else "groq"
            _schedule_coder_agent(
                task.id,
                task.project_id,
                po_feedback=po_feedback,
                agent_run_id=agent_run_id,
                coding_backend=backend,
            )
        return task

    @staticmethod
    def start_coder_agent(
        task_id: UUID,
        project_id: UUID,
        *,
        po_feedback: str | None = None,
        agent_run_id: UUID | None = None,
        inline_comments: list[dict[str, str | int]] | None = None,
    ) -> None:
        """Schedule coder after DB commit (e.g. diff reject / T064)."""
        _schedule_coder_agent(
            task_id,
            project_id,
            po_feedback=po_feedback,
            agent_run_id=agent_run_id,
            inline_comments=inline_comments,
        )
