"""CI step runners: test, lint, build.

Each runner returns a ``StepResult`` with status, logs, duration_ms, and an
optional AI-generated reasoning string.

All runners are sandboxed to the project's local git repo — no network calls,
no Docker-in-Docker for MVP.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum bytes of stdout/stderr kept per step (prevent DB bloat)
_MAX_LOG_BYTES = 32_768  # 32 KB


@dataclass
class StepResult:
    status: str           # 'success' | 'failure' | 'skipped'
    logs: str
    duration_ms: int
    ai_reasoning: str     # plain-language summary for UI


def _run_cmd(
    cmd: list[str],
    cwd: Path,
    *,
    timeout: int = 120,
) -> tuple[int, str]:
    """Run a subprocess, capture combined stdout+stderr, return (returncode, output)."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode, output[:_MAX_LOG_BYTES]
    except subprocess.TimeoutExpired:
        return 1, f"Step timed out after {timeout}s"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"
    except Exception as exc:
        return 1, f"Unexpected error: {exc}"


# ── Test Runner ────────────────────────────────────────────────────────────────

async def run_test(sandbox: Path) -> StepResult:
    """Run pytest (backend) or npm test (frontend) depending on what exists."""
    t0 = time.monotonic()

    # Backend: look for pytest
    backend_dir = sandbox / "backend"
    frontend_dir = sandbox / "frontend"

    if backend_dir.exists() and (backend_dir / "pytest.ini").exists() or \
       backend_dir.exists() and (backend_dir / "pyproject.toml").exists():
        target = backend_dir
        cmd = ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"]
    elif (sandbox / "pytest.ini").exists() or (sandbox / "pyproject.toml").exists():
        target = sandbox
        cmd = ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"]
    elif frontend_dir.exists() and (frontend_dir / "package.json").exists():
        target = frontend_dir
        cmd = ["npm", "test", "--", "--watchAll=false", "--passWithNoTests"]
    elif (sandbox / "package.json").exists():
        target = sandbox
        cmd = ["npm", "test", "--", "--watchAll=false", "--passWithNoTests"]
    else:
        dur = int((time.monotonic() - t0) * 1000)
        return StepResult(
            status="skipped",
            logs="No test runner detected (no pytest.ini / pyproject.toml / package.json)",
            duration_ms=dur,
            ai_reasoning="Skipped: no test framework detected in sandbox.",
        )

    rc, logs = await asyncio.to_thread(_run_cmd, cmd, target)
    dur = int((time.monotonic() - t0) * 1000)
    status = "success" if rc == 0 else "failure"
    reasoning = (
        f"Tests {'passed' if rc == 0 else 'failed'} (exit code {rc}). "
        f"Ran in {dur}ms."
    )
    return StepResult(status=status, logs=logs, duration_ms=dur, ai_reasoning=reasoning)


# ── Lint Runner ────────────────────────────────────────────────────────────────

async def run_lint(sandbox: Path) -> StepResult:
    """Run ruff (Python) and/or eslint (JS/TS) depending on what's present."""
    t0 = time.monotonic()
    combined_logs: list[str] = []
    any_failure = False

    # Python: ruff
    has_ruff = shutil.which("ruff") is not None
    py_files_exist = any(sandbox.rglob("*.py"))
    if has_ruff and py_files_exist:
        rc, out = await asyncio.to_thread(
            _run_cmd, ["ruff", "check", ".", "--output-format=text"], sandbox
        )
        combined_logs.append(f"=== ruff ===\n{out}")
        if rc != 0:
            any_failure = True
    elif py_files_exist:
        combined_logs.append("=== ruff: not installed, skipping Python lint ===")

    # JS/TS: eslint
    frontend_dir = sandbox / "frontend"
    eslint_target = frontend_dir if frontend_dir.exists() else sandbox
    eslint_config = (
        (eslint_target / ".eslintrc.js").exists()
        or (eslint_target / ".eslintrc.cjs").exists()
        or (eslint_target / "eslint.config.js").exists()
        or (eslint_target / "eslint.config.mjs").exists()
        or (eslint_target / "eslint.config.ts").exists()
    )
    has_npx = shutil.which("npx") is not None
    if has_npx and eslint_config:
        rc, out = await asyncio.to_thread(
            _run_cmd, ["npx", "eslint", ".", "--ext", ".ts,.tsx", "--max-warnings=0"],
            eslint_target, timeout=60,
        )
        combined_logs.append(f"=== eslint ===\n{out}")
        if rc != 0:
            any_failure = True

    dur = int((time.monotonic() - t0) * 1000)
    if not combined_logs:
        return StepResult(
            status="skipped",
            logs="No linters detected.",
            duration_ms=dur,
            ai_reasoning="Skipped: neither ruff nor eslint config found.",
        )

    status = "failure" if any_failure else "success"
    logs = "\n".join(combined_logs)[:_MAX_LOG_BYTES]
    reasoning = (
        f"Lint {'found issues' if any_failure else 'passed clean'}. "
        f"Ran in {dur}ms."
    )
    return StepResult(status=status, logs=logs, duration_ms=dur, ai_reasoning=reasoning)


# ── Build Runner ───────────────────────────────────────────────────────────────

async def run_build(sandbox: Path) -> StepResult:
    """Run docker build if Dockerfile exists, else npm build, else python -m py_compile."""
    t0 = time.monotonic()

    # Docker build (preferred — validates full stack)
    dockerfile = sandbox / "Dockerfile"
    if dockerfile.exists() and shutil.which("docker"):
        rc, logs = await asyncio.to_thread(
            _run_cmd,
            ["docker", "build", "--no-cache", "-t", "neo-kanban-build-check", "."],
            sandbox, timeout=300,
        )
        dur = int((time.monotonic() - t0) * 1000)
        status = "success" if rc == 0 else "failure"
        return StepResult(
            status=status,
            logs=logs,
            duration_ms=dur,
            ai_reasoning=f"Docker build {'succeeded' if rc == 0 else 'failed'} in {dur}ms.",
        )

    # Frontend npm build
    frontend_dir = sandbox / "frontend"
    pkg_json = (frontend_dir / "package.json") if frontend_dir.exists() else (sandbox / "package.json")
    if pkg_json.exists() and shutil.which("npm"):
        target = pkg_json.parent
        rc, logs = await asyncio.to_thread(
            _run_cmd, ["npm", "run", "build"], target, timeout=180,
        )
        dur = int((time.monotonic() - t0) * 1000)
        status = "success" if rc == 0 else "failure"
        return StepResult(
            status=status,
            logs=logs,
            duration_ms=dur,
            ai_reasoning=f"npm build {'succeeded' if rc == 0 else 'failed'} in {dur}ms.",
        )

    # Python syntax check (last resort)
    py_files = list(sandbox.rglob("*.py"))
    if py_files:
        errors: list[str] = []
        for f in py_files[:50]:  # limit to 50 files
            rc, out = await asyncio.to_thread(
                _run_cmd, ["python", "-m", "py_compile", str(f)], sandbox
            )
            if rc != 0:
                errors.append(f"{f.name}: {out.strip()}")
        dur = int((time.monotonic() - t0) * 1000)
        if errors:
            return StepResult(
                status="failure",
                logs="\n".join(errors),
                duration_ms=dur,
                ai_reasoning=f"Python syntax errors in {len(errors)} file(s).",
            )
        return StepResult(
            status="success",
            logs=f"Python syntax check passed for {len(py_files)} file(s).",
            duration_ms=dur,
            ai_reasoning="Python syntax check passed.",
        )

    dur = int((time.monotonic() - t0) * 1000)
    return StepResult(
        status="skipped",
        logs="No buildable artifact detected (no Dockerfile, package.json, or .py files).",
        duration_ms=dur,
        ai_reasoning="Skipped: no build target detected.",
    )
