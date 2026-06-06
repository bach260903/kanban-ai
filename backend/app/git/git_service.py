"""Git helpers for per-project sandboxes (US8 / T059)."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Timeout (seconds) for all git subprocess calls.
# Prevents any single git op from hanging indefinitely (e.g. on large node_modules).
_GIT_TIMEOUT = 30

# Lock-contention retry: per-project sandboxes are shared by concurrent agent runs,
# so git commands can collide on .git lock files and exit non-zero. Retry briefly.
_GIT_LOCK_RETRIES = 4
_GIT_LOCK_BACKOFF = 0.25  # seconds, multiplied by attempt number


def _is_lock_error(stderr: str | None) -> bool:
    """True when git stderr indicates transient lock contention (safe to retry)."""
    if not stderr:
        return False
    low = stderr.lower()
    return (
        "could not lock" in low
        or ("unable to create" in low and ".lock" in low)
        or "index.lock" in low
        or "config.lock" in low
        or "file exists" in low
        or "another git process" in low
    )

# Comprehensive .gitignore — covers node_modules, Python envs, build artifacts.
_GITIGNORE_CONTENT = (
    "# Python\n.venv/\nvenv/\n__pycache__/\n*.pyc\n*.pyo\n.pytest_cache/\n"
    ".ruff_cache/\n.mypy_cache/\n*.egg-info/\ndist/\nbuild/\n*.dist-info/\n\n"
    "# Node / Frontend\nnode_modules/\n.npm/\n.yarn/\n.pnp.*\n\n"
    "# Build outputs\ndist/\nbuild/\n.next/\n.nuxt/\n.svelte-kit/\n\n"
    "# Coverage / test\ncoverage/\n.coverage\nhtmlcov/\n\n"
    "# Misc\n.env\n.env.*\n*.log\n.DS_Store\nThumbs.db\n"
)


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
            # whatthepatch yields changes=None for entries with no line changes
            # (binary files, pure mode/rename changes) — skip them instead of crashing.
            for change in (patch.changes or []):
                if change.old is not None and change.new is not None:
                    orig.append(change.line)
                    mod.append(change.line)
                elif change.old is not None:
                    orig.append(change.line)
                elif change.new is not None:
                    mod.append(change.line)
        return "\n".join(orig), "\n".join(mod)

    @staticmethod
    def _git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command with a hard timeout, retrying transient lock contention.

        Per-project sandboxes are shared across concurrent agent tasks, so two git
        commands can race on ``.git/config.lock`` / ``index.lock`` and exit non-zero
        (255 / 128 with "could not lock" / "File exists"). Those are retried a few
        times with a short backoff before the failure is surfaced. Raises on a real
        non-zero exit when ``check=True``.
        """
        import time

        last: subprocess.CompletedProcess | None = None
        for attempt in range(_GIT_LOCK_RETRIES + 1):
            try:
                proc = subprocess.run(
                    ["git", *args],
                    cwd=cwd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=_GIT_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                logger.warning("git %s timed out after %ss in %s", args[0], _GIT_TIMEOUT, cwd)
                raise
            last = proc
            if proc.returncode == 0 or not _is_lock_error(proc.stderr):
                break
            if attempt < _GIT_LOCK_RETRIES:
                logger.warning(
                    "git %s hit a lock in %s (attempt %d/%d) — retrying",
                    args[0], cwd, attempt + 1, _GIT_LOCK_RETRIES,
                )
                time.sleep(_GIT_LOCK_BACKOFF * (attempt + 1))
        assert last is not None
        if check and last.returncode != 0:
            raise subprocess.CalledProcessError(
                last.returncode, ["git", *args], output=last.stdout, stderr=last.stderr
            )
        return last

    @staticmethod
    def _ensure_gitignore(sandbox_path: Path) -> None:
        """Write/update .gitignore — always ensure node_modules and .venv are excluded."""
        gi = sandbox_path / ".gitignore"
        try:
            existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
        except OSError:
            existing = ""
        # Re-write only if key entries are missing to avoid unnecessary disk writes
        missing = any(
            entry not in existing
            for entry in ("node_modules/", ".venv/", "__pycache__/")
        )
        if missing:
            try:
                gi.write_text(_GITIGNORE_CONTENT, encoding="utf-8")
            except OSError:
                pass

    @staticmethod
    def _apply_perf_config(sandbox_path: Path) -> None:
        """Apply git performance settings for Windows (large directories)."""
        configs = [
            ("core.untrackedCache", "true"),      # cache directory scans
            ("feature.manyFiles", "true"),          # optimise for repos with many files
            ("core.fsmonitor", "false"),            # disable fsmonitor (can cause hangs)
            ("status.showUntrackedFiles", "normal"),
        ]
        for key, val in configs:
            try:
                GitService._git(["config", key, val], cwd=sandbox_path, check=False)
            except Exception:
                pass  # perf config failure is non-fatal

    @staticmethod
    def configure_identity(sandbox_path: Path) -> None:
        # Idempotent: skip the writes (and their config.lock window) when identity
        # is already set — every coder run re-enters this on the shared sandbox.
        existing = GitService._git(["config", "--get", "user.email"], cwd=sandbox_path, check=False)
        if (existing.stdout or "").strip() == "coder@local":
            return
        GitService._git(["config", "user.email", "coder@local"], cwd=sandbox_path)
        GitService._git(["config", "user.name", "neo-kanban-coder"], cwd=sandbox_path)

    @staticmethod
    def init_repo(sandbox_path: Path) -> None:
        """Create ``sandbox_path`` and run ``git init`` (standard repo with a **working tree**)."""
        sandbox_path.mkdir(parents=True, exist_ok=True)
        # Write .gitignore BEFORE git init so node_modules is never scanned from the start
        GitService._ensure_gitignore(sandbox_path)
        git_dir = sandbox_path / ".git"
        if not git_dir.exists():
            GitService._git(["init"], cwd=sandbox_path)
        # Apply Windows performance settings immediately after init
        GitService._apply_perf_config(sandbox_path)

    @staticmethod
    def ensure_baseline_commit(sandbox_path: Path) -> None:
        """Create an initial commit so later ``git diff --cached`` has a parent."""
        # Always update .gitignore so node_modules/venv are excluded on every task start
        GitService._ensure_gitignore(sandbox_path)
        # Apply perf config on existing sandboxes too (idempotent)
        GitService._apply_perf_config(sandbox_path)

        r = GitService._git(["rev-parse", "--verify", "HEAD"], cwd=sandbox_path, check=False)
        if r.returncode == 0:
            return  # repo already has commits — nothing to do

        marker = sandbox_path / ".agent_baseline"
        if not marker.exists():
            marker.write_text("", encoding="utf-8")
        GitService._git(["add", ".agent_baseline"], cwd=sandbox_path)
        GitService._git(["commit", "-m", "baseline", "--allow-empty"], cwd=sandbox_path)

    @staticmethod
    def diff(sandbox_path: Path) -> GitDiffResult:
        """Working tree vs index: unified diff, paths, and Monaco ``original`` / ``modified`` text."""
        r = GitService._git(["diff", "--no-color"], cwd=sandbox_path, check=False)
        unified = (r.stdout or "").strip()
        r2 = GitService._git(["diff", "--name-only"], cwd=sandbox_path, check=False)
        files = [line.strip() for line in (r2.stdout or "").splitlines() if line.strip()]
        orig, mod = GitService.unified_to_monaco(unified)
        return GitDiffResult(unified=unified, files=files, original_content=orig, modified_content=mod)

    # Lock files and auto-generated files excluded from diff to keep it readable.
    _DIFF_EXCLUDES = [
        ":!package-lock.json",
        ":!yarn.lock",
        ":!pnpm-lock.yaml",
        ":!poetry.lock",
        ":!Pipfile.lock",
        ":!*.min.js",
        ":!*.min.css",
    ]

    @staticmethod
    def diff_staged(sandbox_path: Path) -> GitDiffResult:
        """Stage all changes and diff index vs ``HEAD`` (agent hand-off to review).

        Lock files and minified assets are excluded from the diff — they are
        auto-generated and add thousands of lines with no review value.
        """
        GitService._ensure_gitignore(sandbox_path)
        GitService._git(["add", "-A"], cwd=sandbox_path, check=False)
        r = GitService._git(
            ["diff", "--cached", "--no-color", "--", ".", *GitService._DIFF_EXCLUDES],
            cwd=sandbox_path, check=False,
        )
        unified = (r.stdout or "").strip()
        r2 = GitService._git(
            ["diff", "--cached", "--name-only", "--", ".", *GitService._DIFF_EXCLUDES],
            cwd=sandbox_path, check=False,
        )
        files = [line.strip() for line in (r2.stdout or "").splitlines() if line.strip()]
        orig, mod = GitService.unified_to_monaco(unified)
        return GitDiffResult(unified=unified, files=files, original_content=orig, modified_content=mod)

    @staticmethod
    def commit_all(sandbox_path: Path, message: str) -> bool:
        """Stage everything and commit on the current branch.

        Returns ``True`` if a commit was created, ``False`` if the tree was clean.
        """
        # Always ensure .gitignore has node_modules BEFORE git add -A
        GitService._ensure_gitignore(sandbox_path)
        GitService._git(["add", "-A"], cwd=sandbox_path, check=False)
        staged = GitService._git(["diff", "--cached", "--quiet"], cwd=sandbox_path, check=False)
        if staged.returncode == 0:
            return False  # nothing staged → nothing to commit
        GitService._git(["commit", "-m", message], cwd=sandbox_path)
        return True

    @staticmethod
    def discard_unstaged(sandbox_path: Path) -> None:
        """Reset tracked files to HEAD, discarding uncommitted edits (e.g. lint --fix).

        Lets a subsequent branch checkout/merge run cleanly after CI steps modified
        the working tree. Untracked files (node_modules, etc.) are left in place.
        """
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=sandbox_path, capture_output=True, text=True,
        )
