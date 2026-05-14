"""Kanban transitions + WIP + coder dispatch (US8 / T056)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from git.exc import GitCommandError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import coder_node
from app.config import settings
from app.exceptions import InvalidTransitionError, NotFoundError, SandboxEscapeError, WIPLimitError
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


async def _run_coder_agent_background(
    task_id: UUID,
    project_id: UUID,
    *,
    po_feedback: str | None = None,
    agent_run_id: UUID | None = None,
    inline_comments: list[dict[str, str | int]] | None = None,
) -> None:
    """Fire-and-forget entry: T058 replaces ``coder_node.run`` body."""
    try:
        payload: dict[str, Any] = {
            "task_id": task_id,
            "project_id": project_id,
        }
        if po_feedback:
            payload["po_feedback"] = po_feedback
        if agent_run_id is not None:
            payload["agent_run_id"] = agent_run_id
        if inline_comments:
            payload["inline_comments"] = inline_comments
        await coder_node.run(payload)
    except Exception:
        logger.exception("Coder agent background task failed task_id=%s", task_id)


def _schedule_coder_agent(
    task_id: UUID,
    project_id: UUID,
    *,
    po_feedback: str | None = None,
    agent_run_id: UUID | None = None,
    inline_comments: list[dict[str, str | int]] | None = None,
) -> None:
    asyncio.create_task(
        _run_coder_agent_background(
            task_id,
            project_id,
            po_feedback=po_feedback,
            agent_run_id=agent_run_id,
            inline_comments=inline_comments,
        )
    )


class KanbanService:
    """Validates task status transitions, enforces WIP = 1, starts coder on ``in_progress``."""

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
            _schedule_coder_agent(
                task.id,
                task.project_id,
                po_feedback=po_feedback,
                agent_run_id=agent_run_id,
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
