"""Kanban transitions + WIP + coder dispatch (US8 / T056)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from git.exc import GitCommandError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import route_coder
from app.agent.nodes import cli_coder_node, coder_node, reviewer_node
from app.config import settings
from app.database import async_session_maker
from app.exceptions import InvalidTransitionError, NotFoundError, SandboxEscapeError, WIPLimitError
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.git.branch_service import BranchService, task_branch_slug
from app.git.git_service import GitService
from app.models.github_config import GitHubConfig
from app.models.task_branch import TaskBranch
from app.models.user import User
from app.services.diff_service import DiffService
from app.services import dependency_service, github_service, notification_service, webhook_service
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


async def get_wip_mode(session: AsyncSession, project_id: UUID) -> str:
    """Return ``user`` when the project has members, else ``project`` (single-user mode)."""
    count = await session.scalar(
        select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project_id)
    )
    return "user" if (count or 0) > 0 else "project"


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


def _build_webhook_payload(event: str, task: Task, actor: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": {"id": str(task.project_id)},
        "task": {"id": str(task.id), "title": task.title},
        "actor": actor,
    }


async def _actor_for_user(session: AsyncSession, user_id: UUID | None) -> dict[str, Any]:
    if user_id is None:
        return {"type": "agent", "id": None, "name": "agent"}
    user = await session.get(User, user_id)
    name = user.display_name if user is not None else "user"
    return {"type": "user", "id": str(user_id), "name": name}


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
    async def on_task_assigned(session: AsyncSession, task: Task, user_id: UUID) -> None:
        try:
            await notification_service.notify_task_assigned(session, task, user_id)
        except Exception:
            logger.exception("notify_task_assigned failed task_id=%s", task.id)

    @staticmethod
    async def on_task_needs_review(
        session: AsyncSession,
        task: Task,
        *,
        current_user_id: UUID | None = None,
    ) -> None:
        try:
            await notification_service.notify_task_needs_review(session, task)
        except Exception:
            logger.exception("notify_task_needs_review failed task_id=%s", task.id)
        try:
            actor = await _actor_for_user(session, current_user_id)
            payload = _build_webhook_payload("task.needs_review", task, actor)
            await webhook_service.enqueue_delivery(
                session,
                task.project_id,
                "task.needs_review",
                payload,
            )
        except Exception:
            logger.exception("webhook enqueue task.needs_review failed task_id=%s", task.id)

    @staticmethod
    async def on_agent_error(
        session: AsyncSession,
        task: Task,
        *,
        current_user_id: UUID | None = None,
    ) -> None:
        try:
            await notification_service.notify_agent_error(session, task)
        except Exception:
            logger.exception("notify_agent_error failed task_id=%s", task.id)
        try:
            actor = await _actor_for_user(session, current_user_id)
            payload = _build_webhook_payload("agent.error", task, actor)
            await webhook_service.enqueue_delivery(
                session,
                task.project_id,
                "agent.error",
                payload,
            )
        except Exception:
            logger.exception("webhook enqueue agent.error failed task_id=%s", task.id)

    @staticmethod
    async def _on_task_done(
        session: AsyncSession,
        task: Task,
        *,
        current_user_id: UUID | None = None,
    ) -> None:
        """Fire task.done webhook. GitHub PR is created earlier, before squash-merge."""
        try:
            actor = await _actor_for_user(session, current_user_id)
            payload = _build_webhook_payload("task.done", task, actor)
            await webhook_service.enqueue_delivery(
                session,
                task.project_id,
                "task.done",
                payload,
            )
        except Exception:
            logger.exception("webhook enqueue task.done failed task_id=%s", task.id)

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
        current_user_id: UUID | None = None,
        po_feedback: str | None = None,
        agent_run_id: UUID | None = None,
        defer_coder_start: bool = False,
    ) -> Task:
        task = await TaskService.get(session, task_id)
        from_status = task.status
        previous_assigned = task.assigned_to
        if from_status == to_status:
            return task
        if (from_status, to_status) not in _ALLOWED_MOVES:
            raise InvalidTransitionError(
                f"Cannot move task from {from_status.value} to {to_status.value}."
            )
        if to_status == TaskStatus.IN_PROGRESS:
            await dependency_service.enforce_not_blocked_for_move(session, task)

            member: ProjectMember | None = None
            if current_user_id is not None:
                member = await session.scalar(
                    select(ProjectMember).where(
                        ProjectMember.project_id == task.project_id,
                        ProjectMember.user_id == current_user_id,
                    )
                )
                if task.assigned_to is None:
                    task.assigned_to = current_user_id
                elif task.assigned_to != current_user_id:
                    if member is None or member.role not in (
                        ProjectRole.OWNER,
                        ProjectRole.LEADER,
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Task assigned to another user",
                        )

            wip_mode = await get_wip_mode(session, task.project_id)
            is_privileged = member is not None and member.role in (
                ProjectRole.OWNER,
                ProjectRole.LEADER,
            )
            if is_privileged:
                pass
            elif wip_mode == "user":
                assignee_id = task.assigned_to
                if assignee_id is not None:
                    in_progress_count = await session.scalar(
                        select(func.count())
                        .select_from(Task)
                        .where(
                            Task.project_id == task.project_id,
                            Task.assigned_to == assignee_id,
                            Task.status == TaskStatus.IN_PROGRESS,
                            Task.id != task.id,
                        )
                    )
                    if (in_progress_count or 0) >= 1:
                        raise WIPLimitError(
                            "WIP limit: only one task may be in progress per developer."
                        )
            elif await TaskService.count_in_progress(session, task.project_id) >= 1:
                raise WIPLimitError("WIP limit: only one task may be in progress per project.")

        branch_name: str | None = None
        if from_status == TaskStatus.REVIEW and to_status == TaskStatus.DONE:
            branch_row = await session.scalar(
                select(TaskBranch).where(TaskBranch.task_id == task.id)
            )
            if branch_row is not None:
                branch_name = branch_row.branch_name
            sandbox = _sandbox_project_root(task.project_id)

            # ── GitHub: commit staged changes to task branch, push, create PR ──
            # Must happen BEFORE squash_and_merge because that call deletes the branch.
            if branch_name is not None:
                gh_config = await session.scalar(
                    select(GitHubConfig).where(
                        GitHubConfig.project_id == task.project_id,
                        GitHubConfig.enabled.is_(True),
                    )
                )
                if gh_config is not None:
                    try:
                        pushed = await github_service.commit_and_push_branch(
                            gh_config,
                            sandbox,
                            branch_name,
                            f"feat: {task.title}",
                        )
                        if pushed:
                            diff = await DiffService.get_latest_approved_for_task(
                                session,
                                task_id=task.id,
                                project_id=task.project_id,
                            )
                            pr_url = await github_service.create_pull_request(
                                gh_config,
                                task,
                                diff.content if diff else "",
                                branch_name,
                            )
                            logger.info(
                                "GitHub PR created for task_id=%s: %s", task.id, pr_url
                            )
                    except Exception:
                        logger.exception(
                            "GitHub push/PR failed task_id=%s", task.id
                        )

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

        if (
            to_status == TaskStatus.IN_PROGRESS
            and task.assigned_to is not None
            and task.assigned_to != previous_assigned
        ):
            await KanbanService.on_task_assigned(session, task, task.assigned_to)

        if to_status == TaskStatus.REVIEW:
            await KanbanService.on_task_needs_review(
                session,
                task,
                current_user_id=current_user_id,
            )

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
            await KanbanService._on_task_done(
                session,
                task,
                current_user_id=current_user_id,
            )

        if to_status == TaskStatus.DONE and from_status != TaskStatus.DONE:
            unlocked_ids = await dependency_service.unlock_dependents(session, task.id)
            for unlocked_id in unlocked_ids:
                logger.info(
                    "Unlocked dependent task_id=%s after task_id=%s moved to done",
                    unlocked_id,
                    task.id,
                )
                unlocked_task = await session.get(Task, unlocked_id)
                if unlocked_task is not None and unlocked_task.assigned_to is not None:
                    try:
                        await notification_service.notify_task_unblocked(
                            session,
                            unlocked_task,
                            unlocked_task.assigned_to,
                        )
                    except Exception:
                        logger.exception(
                            "notify_task_unblocked failed task_id=%s",
                            unlocked_id,
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
