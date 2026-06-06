"""Kanban transitions + WIP + coder dispatch (US8 / T056)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import subprocess

from fastapi import HTTPException, status
from git.exc import GitCommandError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import route_coder
from app.agent.nodes import cli_coder_node, coder_node, reviewer_node
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
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

_MAX_CI_RETRIES = 2
_CI_POLL_INTERVAL = 5   # seconds
_CI_TIMEOUT = 300       # 5 minutes


async def _run_ci_gate(project_id: UUID, task_id: UUID | None) -> tuple[bool, str]:
    """Trigger pipeline, wait synchronously, return (passed, failure_report).

    Opens its own DB sessions so it can be called from any background context.
    Returns (True, "") on success or timeout-as-skip; (False, report) on failure.
    """
    from app.pipeline.pipeline_service import PipelineService  # avoid circular at module level

    try:
        sandbox = _sandbox_project_root(project_id)
        async with async_session_maker() as session:
            run = await PipelineService.create_and_trigger(
                session,
                project_id=project_id,
                task_id=task_id,
                sandbox=sandbox,
                triggered_by="agent_ci_gate",
            )
            run_id = run.id

        elapsed = 0
        run_status = PipelineRunStatus.QUEUED
        while elapsed < _CI_TIMEOUT:
            await asyncio.sleep(_CI_POLL_INTERVAL)
            elapsed += _CI_POLL_INTERVAL
            async with async_session_maker() as session:
                fresh = await session.get(PipelineRun, run_id)
                if fresh is None:
                    return False, "CI pipeline run disappeared from DB."
                run_status = fresh.status
                if run_status not in (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING):
                    steps = list(fresh.steps or [])
                    break
        else:
            return True, ""  # timeout → don't block forever, let human review

        if run_status == PipelineRunStatus.SUCCESS:
            return True, ""

        lines = [f"CI pipeline failed (status={run_status})."]
        for step in steps:
            if step.status.value in ("failure", "error") and step.logs:
                tail = "\n".join(step.logs.splitlines()[-40:])
                lines.append(f"\n### {step.step_key}\n```\n{tail}\n```")
        return False, "\n".join(lines)

    except Exception as exc:
        logger.exception("CI gate error project_id=%s", project_id)
        return True, ""  # on unexpected error, don't block — let human review


def _sandbox_project_root(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


async def _github_push_pr_bg(
    project_id: UUID,
    task_id: UUID,
    branch_name: str,
    sandbox: Path,
    task_title: str,
) -> None:
    """Background: push task branch to GitHub and open a PR. Opens its own DB session."""
    try:
        async with async_session_maker() as session:
            gh_config = await session.scalar(
                select(GitHubConfig).where(
                    GitHubConfig.project_id == project_id,
                    GitHubConfig.enabled.is_(True),
                )
            )
            if gh_config is None:
                return
            pushed = await github_service.commit_and_push_branch(
                gh_config, sandbox, branch_name, f"feat: {task_title}"
            )
            if not pushed:
                return
            task = await session.get(Task, task_id)
            diff = await DiffService.get_latest_approved_for_task(
                session, task_id=task_id, project_id=project_id
            )
            pr_url = await github_service.create_pull_request(
                gh_config, task, diff.content if diff else "", branch_name
            )
            logger.info("GitHub PR created for task_id=%s: %s", task_id, pr_url)
    except Exception:
        logger.exception("_github_push_pr_bg failed task_id=%s", task_id)


async def _memory_export_bg(project_id: UUID, task_id: UUID) -> None:
    """Background: write memory entry + export MEMORY.md + git commit. Opens its own DB session."""
    try:
        async with async_session_maker() as session:
            diff = await DiffService.get_latest_approved_for_task(
                session, task_id=task_id, project_id=project_id
            )
            if diff is not None:
                await MemoryService.create_entry(session, project_id, task_id, diff)
                await MemoryService.export_memory_file(session, project_id)
            sandbox = _sandbox_project_root(project_id)
            await asyncio.to_thread(GitService.commit_all, sandbox, "chore: update MEMORY.md")
    except Exception:
        logger.exception("_memory_export_bg failed project_id=%s", project_id)


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
                # Failed run returns the task to To do so it stays visible and retryable.
                task.status = TaskStatus.TODO
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
    _ci_retry_count: int = 0,
    _crash_retry_count: int = 0,
) -> None:
    """Fire-and-forget entry: Coder → CI gate → (pass) Reviewer  |  (fail, retry) re-Coder."""
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

        # Coder handled its own error (task reset to TODO, run finalised, notification sent).
        # Don't proceed to CI or reviewer — there is nothing to review.
        if state.get("error"):
            return

        # ── CI gate ──────────────────────────────────────────────────────────
        ci_passed, ci_report = await _run_ci_gate(project_id, task_id)

        if not ci_passed and _ci_retry_count < _MAX_CI_RETRIES:
            logger.info(
                "CI failed (attempt %d/%d) task_id=%s — re-dispatching coder with error context",
                _ci_retry_count + 1, _MAX_CI_RETRIES, task_id,
            )
            _schedule_coder_agent(
                task_id, project_id,
                po_feedback=ci_report,
                agent_run_id=agent_run_id,
                coding_backend=coding_backend,
                _ci_retry_count=_ci_retry_count + 1,
            )
            return

        # CI passed (or max retries reached) → reviewer
        if ci_report:
            state["ci_failure_report"] = ci_report  # human will see it in review panel
        await reviewer_node.run(state)

    except Exception as exc:
        logger.exception("Coder agent background task failed task_id=%s", task_id)
        # Retry once on transient crash (LLM timeout, network error, etc.)
        # before marking the task as failed so human doesn't need to intervene.
        if _crash_retry_count < 1:
            logger.info("Coder crashed (attempt %d) — retrying task_id=%s", _crash_retry_count + 1, task_id)
            _schedule_coder_agent(
                task_id, project_id,
                po_feedback=po_feedback,
                agent_run_id=agent_run_id,
                inline_comments=inline_comments,
                coding_backend=coding_backend,
                _ci_retry_count=_ci_retry_count,
                _crash_retry_count=_crash_retry_count + 1,
            )
            return
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
    _ci_retry_count: int = 0,
    _crash_retry_count: int = 0,
) -> None:
    asyncio.create_task(
        _run_coder_agent_background(
            task_id,
            project_id,
            po_feedback=po_feedback,
            agent_run_id=agent_run_id,
            inline_comments=inline_comments,
            coding_backend=coding_backend,
            _ci_retry_count=_ci_retry_count,
            _crash_retry_count=_crash_retry_count,
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
    async def retry_pipeline_failure_with_coder(
        session: AsyncSession,
        project_id: UUID,
        task_id: UUID,
        failure_summary: str,
    ) -> bool:
        """Self-heal a CI failure by re-running the Coder with the error as feedback.

        System-controlled retry: a DONE task whose pipeline failed is sent back to
        In Progress and the Coder is re-dispatched with the CI error text as PO
        feedback. The Coder (which has tools + can run tests) fixes the code, the diff
        goes to Review for the PO, then re-runs CI. Returns True if a retry was kicked.

        Bounding (number of attempts) is enforced by the caller (executor) so this
        only fires when another auto-fix cycle is allowed.
        """
        task = await session.get(Task, task_id)
        if task is None or task.status != TaskStatus.DONE:
            return False
        sandbox = _sandbox_project_root(project_id)
        try:
            # Idempotent: checks out the existing task branch (it isn't merged on a
            # failed pipeline) so the Coder edits the right working tree.
            await BranchService.create_task_branch(session, task_id, sandbox)
        except Exception:
            logger.warning("retry_pipeline_failure: could not ensure task branch %s", task_id, exc_info=True)
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await session.commit()
        project = await session.get(Project, project_id)
        backend = str(project.coding_backend) if project is not None else "groq"
        logger.info("retry_pipeline_failure: re-dispatching coder for task %s", task_id)
        _schedule_coder_agent(
            task_id,
            project_id,
            po_feedback=failure_summary,
            coding_backend=backend,
        )
        return True

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
            # The per-assignee WIP=1 rule is backed by the partial unique index
            # ``one_in_progress_per_assignee`` (project_id, assigned_to WHERE
            # status='in_progress'), so it holds even for owners/leaders. Their
            # privilege only lets them act on tasks assigned to OTHERS (the 403
            # above) — it does NOT let them stack two in-progress tasks on a
            # single assignee. Skipping this check would let the move reach the
            # DB index and surface as a raw UniqueViolation (HTTP 500) instead
            # of a clean WIP conflict (HTTP 409). Owners/leaders still bypass the
            # stricter project-wide limit so they can run work in parallel across
            # different developers.
            if is_privileged or wip_mode == "user":
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

            # Fire-and-forget: git commit runs in background — pipeline executor
            # only accesses the sandbox seconds later so the commit is always done first.
            _commit_msg = f"feat: {task.title}"
            _sandbox_commit = sandbox
            async def _commit_bg() -> None:
                try:
                    await asyncio.to_thread(GitService.commit_all, _sandbox_commit, _commit_msg)
                except Exception:
                    logger.exception("Background commit_all failed (task %s)", task_id)
            asyncio.create_task(_commit_bg(), name=f"git-commit-{task_id}")

            # GitHub push + PR: fire-and-forget background task (2-13s network I/O).
            # Does not block the HTTP response; failures are logged, never surface to user.
            if branch_name is not None:
                asyncio.create_task(
                    _github_push_pr_bg(
                        project_id=task.project_id,
                        task_id=task.id,
                        branch_name=branch_name,
                        sandbox=sandbox,
                        task_title=task.title,
                    ),
                    name=f"github-push-{task.id}",
                )

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
            # Fire-and-forget: git init/configure/branch are disk-heavy (300-1100 ms).
            # The coder agent calls an LLM first (2-30 s), so sandbox is always ready
            # before the agent touches any files.
            _sandbox_init = _sandbox_project_root(task.project_id)
            _init_task_id = task.id
            _init_project_id = task.project_id

            async def _git_init_bg() -> None:
                try:
                    await asyncio.to_thread(GitService.init_repo, _sandbox_init)
                    await asyncio.to_thread(GitService.configure_identity, _sandbox_init)
                    await asyncio.to_thread(GitService.ensure_baseline_commit, _sandbox_init)
                    async with async_session_maker() as bg_session:
                        await BranchService.create_task_branch(bg_session, _init_task_id, _sandbox_init)
                        await bg_session.commit()
                except Exception:
                    logger.exception(
                        "Background git init FAILED for task_id=%s — reverting to TODO",
                        _init_task_id,
                    )
                    # Revert the task so the user can retry
                    try:
                        async with async_session_maker() as bg_session:
                            t = await bg_session.get(Task, _init_task_id)
                            if t is not None and t.status == TaskStatus.IN_PROGRESS:
                                t.status = TaskStatus.TODO
                                t.updated_at = datetime.now(timezone.utc)
                                await bg_session.commit()
                    except Exception:
                        logger.exception("Failed to revert task_id=%s after git init failure", _init_task_id)

            asyncio.create_task(_git_init_bg(), name=f"git-init-{task.id}")
        if to_status == TaskStatus.DONE and from_status == TaskStatus.REVIEW:
            # ── Trigger CI/CD pipeline only if no passing run exists yet ──────
            # The agent's ci_gate_node already ran CI before moving to REVIEW.
            # Re-running is wasteful when code hasn't changed since that run.
            try:
                from app.pipeline.pipeline_service import PipelineService
                _pipeline_sandbox = _sandbox_project_root(task.project_id)
                _branch_row = await session.scalar(
                    select(TaskBranch).where(TaskBranch.task_id == task.id)
                )
                _last_success = await session.scalar(
                    select(PipelineRun)
                    .where(
                        PipelineRun.task_id == task.id,
                        PipelineRun.status == PipelineRunStatus.SUCCESS,
                    )
                    .order_by(PipelineRun.created_at.desc())
                    .limit(1)
                )
                if _last_success is None:
                    await PipelineService.create_and_trigger(
                        session,
                        project_id=task.project_id,
                        task_id=task.id,
                        sandbox=_pipeline_sandbox,
                        triggered_by="task_approved",
                        branch_name=_branch_row.branch_name if _branch_row else None,
                    )
                else:
                    logger.info(
                        "Skipping CI re-run for task_id=%s — already has a passing run (%s)",
                        task.id, _last_success.id,
                    )
            except Exception:
                logger.exception("Failed to create pipeline run for task_id=%s", task.id)

            # Memory export + MEMORY.md commit: fire-and-forget background task.
            asyncio.create_task(
                _memory_export_bg(task.project_id, task.id),
                name=f"memory-export-{task.id}",
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
        coding_backend: str = "groq",
    ) -> None:
        """Schedule coder after DB commit (e.g. diff reject / T064)."""
        _schedule_coder_agent(
            task_id,
            project_id,
            po_feedback=po_feedback,
            agent_run_id=agent_run_id,
            inline_comments=inline_comments,
            coding_backend=coding_backend,
        )
