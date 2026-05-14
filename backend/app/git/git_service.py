"""Git helpers for per-project sandboxes (US8 / T059)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitDiffResult:
    """Output of ``GitService.diff`` / ``GitService.diff_staged`` (unified + Monaco pair)."""

    unified: str
    files: list[str]
    original_content: str
    modified_content: str


class GitService:
    """Working-tree git repos under each sandbox (agent edits + review diffs)."""

    @staticmethod
    def unified_to_monaco(unified: str) -> tuple[str, str]:
        """Map a unified diff string to ``(original, modified)`` text for Monaco (D-04)."""
        if not unified.strip():
            return "", ""
        try:
            from whatthepatch import parse_patch

            patches = list(parse_patch(unified))
        except Exception:
            return unified, unified
        orig: list[str] = []
        mod: list[str] = []
        for patch in patches:
            for change in patch.changes:
                if change.old is not None and change.new is not None:
                    orig.append(change.line)
                    mod.append(change.line)
                elif change.old is not None:
                    orig.append(change.line)
                elif change.new is not None:
                    mod.append(change.line)
        return "\n".join(orig), "\n".join(mod)

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
        """Create ``sandbox_path`` and run ``git init`` (standard repo with a **working tree**).

        A *bare* repository (``git init --bare``) has no checkout for agent file tools, so the
        MVP uses a normal repository rooted at the sandbox directory (T058 coder_node).
        """
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
    def diff(sandbox_path: Path) -> GitDiffResult:
        """Working tree vs index: unified diff, paths, and Monaco ``original`` / ``modified`` text."""
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
        orig, mod = GitService.unified_to_monaco(unified)
        return GitDiffResult(unified=unified, files=files, original_content=orig, modified_content=mod)

    @staticmethod
    def diff_staged(sandbox_path: Path) -> GitDiffResult:
        """Stage all changes and diff index vs ``HEAD`` (agent hand-off to review)."""
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
        orig, mod = GitService.unified_to_monaco(unified)
        return GitDiffResult(unified=unified, files=files, original_content=orig, modified_content=mod)
