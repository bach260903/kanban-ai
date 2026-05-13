"""Minimal git operations on a per-project sandbox directory (T058; extended in T059)."""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitService:
    """Initialize a repo under ``SANDBOX_ROOT/{project_id}`` and read unified diffs."""

    @staticmethod
    def configure_identity(sandbox_path: Path) -> None:
        subprocess.run(
            ["git", "config", "user.email", "coder@local"],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "neo-kanban-coder"],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def init_repo(sandbox_path: Path) -> None:
        sandbox_path.mkdir(parents=True, exist_ok=True)
        git_dir = sandbox_path / ".git"
        if not git_dir.exists():
            subprocess.run(
                ["git", "init"],
                cwd=sandbox_path,
                check=True,
                capture_output=True,
                text=True,
            )

    @staticmethod
    def ensure_baseline_commit(sandbox_path: Path) -> None:
        """Create an initial commit so later ``git diff --cached`` has a parent."""
        r = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            return
        marker = sandbox_path / ".agent_baseline"
        if not marker.exists():
            marker.write_text("", encoding="utf-8")
        subprocess.run(
            ["git", "add", ".agent_baseline"],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "baseline", "--allow-empty"],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def diff(sandbox_path: Path) -> tuple[str, list[str]]:
        """Return ``(unified_diff_text, files_changed)`` for the working tree."""
        r = subprocess.run(
            ["git", "diff", "--no-color"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
        )
        unified = (r.stdout or "").strip()
        r2 = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
        )
        files = [line.strip() for line in (r2.stdout or "").splitlines() if line.strip()]
        return unified, files

    @staticmethod
    def diff_staged(sandbox_path: Path) -> tuple[str, list[str]]:
        """Stage all changes and return cached diff vs HEAD (agent output for review)."""
        subprocess.run(
            ["git", "add", "-A"],
            cwd=sandbox_path,
            check=True,
            capture_output=True,
            text=True,
        )
        r = subprocess.run(
            ["git", "diff", "--cached", "--no-color"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
        )
        unified = (r.stdout or "").strip()
        r2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=sandbox_path,
            capture_output=True,
            text=True,
        )
        files = [line.strip() for line in (r2.stdout or "").splitlines() if line.strip()]
        return unified, files
