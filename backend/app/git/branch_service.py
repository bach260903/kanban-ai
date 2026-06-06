"""Per-task sandbox branches and squash-merge (US15 / T102)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from git import Repo
from git.exc import GitCommandError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.task import Task, TaskStatus
from app.models.task_branch import TaskBranch, TaskBranchStatus

logger = logging.getLogger(__name__)


def task_branch_slug(task_id: UUID) -> str:
    """Return ``task/{first_8_hex_of_uuid}`` (lowercase), per data-model / plan."""
    short = str(task_id).replace("-", "")[:8].lower()
    return f"task/{short}"


def _integration_branch_name(repo: Repo) -> str:
    for candidate in ("main", "master"):
        if candidate in repo.heads:
            return candidate
    return repo.active_branch.name


def _commit_if_dirty(repo: Repo, message: str = "chore: auto-commit before branch switch") -> None:
    """Stage and commit any dirty working-tree changes on the current branch.

    Prevents 'your local changes would be overwritten by checkout' errors when
    files like MEMORY.md are written after the last explicit commit.
    """
    try:
        repo.git.add("-A")
        staged = repo.git.diff("--cached", "--name-only").strip()
        if staged:
            repo.git.commit("-m", message)
            logger.debug("auto-committed dirty files before branch switch: %s", staged)
    except GitCommandError:
        logger.warning("auto-commit before branch switch failed; proceeding anyway", exc_info=True)


def _sync_ensure_task_branch(sandbox_path: Path, branch_name: str) -> None:
    repo = Repo(str(sandbox_path.resolve()))
    _commit_if_dirty(repo)
    if branch_name in repo.heads:
        repo.git.checkout(branch_name)
        return
    base = _integration_branch_name(repo)
    repo.git.checkout(base)
    repo.git.checkout("-b", branch_name)


def _sync_recreate_task_branch(sandbox_path: Path, branch_name: str) -> None:
    """Delete the existing branch (if any) and re-create it from the current integration HEAD.

    Used when a conflicted task is retried so the new branch picks up all changes that
    landed on main after the conflict was detected.
    """
    repo = Repo(str(sandbox_path.resolve()))
    integration = _integration_branch_name(repo)
    _commit_if_dirty(repo)
    # Make sure we are NOT on the branch we are about to delete
    if repo.active_branch.name == branch_name:
        repo.git.checkout(integration)
    if branch_name in repo.heads:
        try:
            repo.git.branch("-D", branch_name)
            logger.info("Deleted conflicted branch %s before retry", branch_name)
        except GitCommandError:
            logger.warning("Could not delete conflicted branch %s", branch_name, exc_info=True)
    repo.git.checkout(integration)
    repo.git.checkout("-b", branch_name)
    logger.info("Re-created branch %s from %s for conflict retry", branch_name, integration)


def _sync_abort_squash_attempt(sandbox_path: Path) -> None:
    repo = Repo(str(sandbox_path.resolve()))
    try:
        repo.git.reset("--hard", "HEAD")
    except GitCommandError:
        logger.warning("git reset --hard after failed squash", exc_info=True)


def _sync_squash_merge_to_integration(sandbox_path: Path, branch_name: str) -> None:
    repo = Repo(str(sandbox_path.resolve()))
    integration = _integration_branch_name(repo)
    _commit_if_dirty(repo)
    repo.git.checkout(integration)
    repo.git.merge("--squash", branch_name)
    staged = repo.git.diff("--cached", "--name-only")
    if not (staged or "").strip():
        try:
            repo.git.branch("-d", branch_name)
        except GitCommandError:
            logger.warning("Could not delete branch %s (already up to date squash)", branch_name)
        return
    repo.git.commit("-m", f"Squash merge {branch_name} into {integration}")
    try:
        repo.git.branch("-d", branch_name)
    except GitCommandError:
        logger.warning("Could not delete merged branch %s in %s", branch_name, sandbox_path)


class BranchService:
    """Git branch lifecycle for a task sandbox + ``task_branches`` rows."""

    @staticmethod
    async def create_task_branch(
        session: AsyncSession,
        task_id: UUID,
        sandbox_path: Path,
    ) -> TaskBranch:
        """Create ``task/{{uuid8}}`` from integration HEAD and persist ``task_branches``."""
        existing = await session.scalar(select(TaskBranch).where(TaskBranch.task_id == task_id))
        if existing is not None:
            if existing.status == TaskBranchStatus.CONFLICT:
                # Task was previously stuck in conflict — delete the old branch and
                # re-create from current integration HEAD so the retry starts clean.
                await asyncio.to_thread(
                    _sync_recreate_task_branch, sandbox_path, existing.branch_name
                )
                existing.status = TaskBranchStatus.ACTIVE
                existing.merged_at = None
                await session.flush()
            else:
                await asyncio.to_thread(_sync_ensure_task_branch, sandbox_path, existing.branch_name)
            return existing

        branch_name = task_branch_slug(task_id)
        try:
            await asyncio.to_thread(_sync_ensure_task_branch, sandbox_path, branch_name)
        except GitCommandError:
            logger.exception("git create/checkout branch failed task_id=%s branch=%s", task_id, branch_name)
            raise

        row = TaskBranch(
            task_id=task_id,
            branch_name=branch_name,
            status=TaskBranchStatus.ACTIVE,
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def detect_conflict(session: AsyncSession, task_id: UUID) -> None:
        """Mark ``task_branches`` and ``tasks`` as conflict after a failed merge (GitCommandError path)."""
        row = await session.scalar(select(TaskBranch).where(TaskBranch.task_id == task_id))
        if row is not None:
            row.status = TaskBranchStatus.CONFLICT
        task = await session.get(Task, task_id)
        if task is not None:
            task.status = TaskStatus.TODO
            task.updated_at = datetime.now(timezone.utc)
        await session.flush()

    @staticmethod
    async def squash_and_merge(
        session: AsyncSession,
        task_id: UUID,
        sandbox_path: Path,
    ) -> TaskBranch:
        """``git merge --squash`` task branch into main/master, single commit; mark branch merged."""
        row = await session.scalar(select(TaskBranch).where(TaskBranch.task_id == task_id))
        if row is None:
            raise NotFoundError("No task branch for this task.")
        if row.status != TaskBranchStatus.ACTIVE:
            raise ValueError(f"Cannot squash branch in status {row.status!r}.")

        branch_name = row.branch_name
        try:
            await asyncio.to_thread(_sync_squash_merge_to_integration, sandbox_path, branch_name)
        except GitCommandError:
            await asyncio.to_thread(_sync_abort_squash_attempt, sandbox_path)
            await BranchService.detect_conflict(session, task_id)
            raise

        row.status = TaskBranchStatus.MERGED
        row.merged_at = datetime.now(timezone.utc)
        await session.flush()
        return row
