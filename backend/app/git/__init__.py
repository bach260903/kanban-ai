"""Git utilities for sandbox workspaces."""

from __future__ import annotations

from app.git.git_service import GitDiffResult, GitService

__all__ = ["BranchService", "GitDiffResult", "GitService", "task_branch_slug"]


def __getattr__(name: str):
    if name == "BranchService":
        from app.git.branch_service import BranchService as _BranchService

        return _BranchService
    if name == "task_branch_slug":
        from app.git.branch_service import task_branch_slug as _task_branch_slug

        return _task_branch_slug
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
