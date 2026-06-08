"""CI step runners: test, lint, build.

Each runner returns a ``StepResult`` with status, logs, duration_ms, and an
optional AI-generated reasoning string.

Runners are designed to work across project shapes the AI agent may produce:
Python projects, Node/JS/TS projects, and loose individual source files with
no build config. Each step degrades gracefully — it tries the richest check
available and falls back to syntax/type checks so CI stays meaningful even for
ad-hoc output, only reporting ``skipped`` when there is genuinely nothing to do.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum bytes of stdout/stderr kept per step (prevent DB bloat)
_MAX_LOG_BYTES = 32_768  # 32 KB

# Directories never scanned for source files
_IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", ".venv", "venv",
    "__pycache__", ".next", "coverage", ".pytest_cache", ".mypy_cache",
}

_KNOWN_TEST_RUNNERS = {"jest", "vitest", "mocha", "jasmine", "tap", "ava"}

# Jest configuration filenames in priority order (highest priority first).
# Jest fails with "Multiple configurations found" when more than one exists;
# this list drives the auto-dedup that runs before every npm test invocation.
_JEST_CONFIG_PRIORITY = [
    "jest.config.js",
    "jest.config.ts",
    "jest.config.cjs",
    "jest.config.mjs",
    "jest.config.json",
]


def _dedup_jest_configs(target: Path) -> str | None:
    """Remove duplicate Jest config files, keeping the highest-priority one.

    The Coder agent sometimes creates ``jest.config.js`` and then, when a test
    fails for an unrelated reason, also writes ``jest.config.cjs`` as a retry
    attempt — leaving two config files that make Jest error with
    "Multiple configurations found".

    We keep the first match in ``_JEST_CONFIG_PRIORITY`` order and delete the
    rest.  Returns a log line describing the action, or ``None`` if nothing was
    removed (no-op for projects with a single config or no Jest at all).
    """
    found = [name for name in _JEST_CONFIG_PRIORITY if (target / name).exists()]
    if len(found) <= 1:
        return None

    keep = found[0]
    removed: list[str] = []
    for name in found[1:]:
        try:
            (target / name).unlink()
            removed.append(name)
        except OSError as exc:
            logger.warning("dedup_jest_configs: could not remove %s/%s: %s", target, name, exc)

    if not removed:
        return None
    msg = (
        f"[CI auto-fix] Removed duplicate Jest config(s): {', '.join(removed)} "
        f"— keeping {keep}. "
        "The Coder agent created multiple Jest config files; CI removed extras."
    )
    logger.info(msg)
    return msg


@dataclass
class StepResult:
    status: str           # 'success' | 'failure' | 'skipped'
    logs: str
    duration_ms: int
    ai_reasoning: str     # plain-language summary for UI


# ── Helpers ──────────────────────────────────────────────────────────────────

def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """All files under ``root`` matching ``suffixes``, skipping ignored dirs."""
    out: list[Path] = []
    if not root.exists():
        return out
    try:
        for p in root.rglob("*"):
            if p.is_dir():
                continue
            if any(part in _IGNORE_DIRS for part in p.parts):
                continue
            if p.suffix in suffixes:
                out.append(p)
    except (OSError, FileNotFoundError) as e:
        # Windows bind-mount issue: some directories (e.g. node_modules/fsevents)
        # may be inaccessible. Log and continue with partial results.
        logger.warning("_iter_files: error scanning %s: %s", root, e)
    return out


def _read_pkg_scripts(pkg_path: Path) -> dict[str, str]:
    """scripts{} block from a package.json, or empty dict on any error."""
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
        return data.get("scripts", {}) or {}
    except Exception:
        return {}


def _has_real_script(scripts: dict[str, str], name: str) -> bool:
    """True if package.json declares a usable (non-placeholder) script."""
    val = scripts.get(name, "")
    if not val:
        return False
    # npm's default placeholder for a missing test script
    if name == "test" and "no test specified" in val:
        return False
    return True


# Tokens that mean a "test" script is actually a Python command, not a Node one.
_PY_TEST_TOKENS = {"pytest", "py.test", "python", "python3", "tox", "nox", "unittest"}


def _is_python_test_script(scripts: dict[str, str]) -> bool:
    """True when package.json's ``test`` script invokes a Python runner.

    The agent sometimes writes a Node ``package.json`` whose test script is
    ``pytest`` (and even lists pytest as an npm dependency). Running ``npm
    install`` then fails with ETARGET because pytest is not an npm package.
    Detecting this lets the test step run pytest instead of npm.
    """
    val = scripts.get("test", "").strip().lower()
    if not val:
        return False
    first = val.split()[0]
    return first in _PY_TEST_TOKENS or "pytest" in val


def _find_tsconfig(sandbox: Path) -> Path | None:
    """Locate the project's tsconfig.json (root, frontend/, or shallow search)."""
    for p in (sandbox / "tsconfig.json", sandbox / "frontend" / "tsconfig.json"):
        if p.exists():
            return p
    for p in sandbox.rglob("tsconfig.json"):
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        return p
    return None


def _tsc_cmd(sandbox: Path, ts_files: list[Path]) -> tuple[list[str], Path]:
    """Build a ``tsc --noEmit`` invocation and its cwd.

    When a tsconfig.json exists, tsc must auto-discover it from the cwd — passing
    files on the command line triggers TS5112 and bypasses the config. Without a
    tsconfig, fall back to explicit files so loose .ts output still gets checked.
    """
    base = ["npx", "--package=typescript", "--yes", "tsc", "--noEmit", "--skipLibCheck"]
    tsconfig = _find_tsconfig(sandbox)
    if tsconfig is not None:
        return base, tsconfig.parent
    # No tsconfig → check loose files, but skip test files (their describe/it/expect
    # globals need a test-runner's @types, which aren't configured here).
    src = [f for f in ts_files if not (f.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")))]
    return base + ["--allowJs", *[str(f) for f in src[:100]]], sandbox


def _run_cmd(
    cmd: list[str],
    cwd: Path,
    *,
    timeout: int = 120,
) -> tuple[int, str]:
    """Run a subprocess, capture combined stdout+stderr, return (returncode, output)."""
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
        return 127, f"Command not found: {cmd[0]}"
    except Exception as exc:
        return 1, f"Unexpected error: {exc}"


def _npm_install(target: Path) -> tuple[int, str]:
    """npm install in ``target`` (network access required)."""
    return _run_cmd(["npm", "install"], target, timeout=180)


def _ensure_test_runner(target: Path) -> None:
    """Install the test runner named in scripts.test if it's missing from node_modules.

    The agent frequently writes ``"test": "jest"`` without adding jest to
    devDependencies, which would otherwise fail with command-not-found.
    """
    pkg_path = target / "package.json"
    if not pkg_path.exists():
        return
    runner = _read_pkg_scripts(pkg_path).get("test", "").split()
    runner_name = runner[0] if runner else ""
    if runner_name not in _KNOWN_TEST_RUNNERS:
        return
    if not (target / "node_modules" / ".bin" / runner_name).exists():
        logger.info("pipeline: installing missing test runner %s", runner_name)
        _run_cmd(["npm", "install", "--save-dev", runner_name], target, timeout=120)


# ── Test Runner ────────────────────────────────────────────────────────────────

# Maps an importable module name to its pip package when they differ.
_MODULE_TO_PIP = {
    "cv2": "opencv-python", "yaml": "pyyaml", "PIL": "pillow", "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn", "dotenv": "python-dotenv", "jwt": "pyjwt",
    "dateutil": "python-dateutil", "psycopg2": "psycopg2-binary",
}
_MISSING_MODULE_RE = re.compile(r"No module named '([\w][\w.]*)'")
_MAX_MODULE_INSTALLS = 6


def _ensure_py_venv(target: Path) -> str:
    """Create an isolated venv (OUTSIDE the sandbox) and install the project's reqs.

    The venv is created in a container-local temp dir, NOT inside the bind-mounted
    sandbox — a venv has ~2000 small files, which (a) would be committed/pushed and
    (b) cripples Docker's host file-sync on Windows. ``--system-site-packages`` lets
    it inherit the container's pytest/ruff. Returns the venv python, or ``"python"``
    if setup fails.
    """
    key = hashlib.sha1(str(target.resolve()).encode()).hexdigest()[:16]
    venv = Path(tempfile.gettempdir()) / "neo-ci-venv" / key
    py = venv / "bin" / "python"
    if not py.exists():
        venv.parent.mkdir(parents=True, exist_ok=True)
        rc, _ = _run_cmd(["python", "-m", "venv", "--system-site-packages", str(venv)], target, timeout=60)
        if rc != 0 or not py.exists():
            return "python"
    if (target / "requirements.txt").exists():
        _run_cmd(
            [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", "requirements.txt"],
            target, timeout=180,
        )
    return str(py)


async def _run_pytest_step(target: Path, t0: float) -> StepResult:
    """Run pytest in ``target``, auto-installing missing third-party modules.

    When the code under test imports a library that isn't installed, pytest fails
    with ``ModuleNotFoundError: No module named 'X'``. Instead of failing the whole
    task, we ``pip install`` X into the project venv and retry — so "unknown module"
    errors heal themselves. Bounded by ``_MAX_MODULE_INSTALLS`` to avoid loops.
    Degrades to ``skipped`` when pytest is unavailable or finds no tests.
    """
    if not _module_available("pytest"):
        dur = int((time.monotonic() - t0) * 1000)
        return StepResult(
            status="skipped",
            logs="pytest is not installed in the CI environment — Python tests skipped.",
            duration_ms=dur,
            ai_reasoning="Skipped: pytest not available in the CI runner.",
        )

    py_exec = await asyncio.to_thread(_ensure_py_venv, target)
    pytest_cmd = [py_exec, "-m", "pytest", "--tb=short", "-q", "--no-header", "-o", "asyncio_mode=auto"]
    installed: list[str] = []
    rc, logs = 1, ""

    for _ in range(_MAX_MODULE_INSTALLS + 1):
        rc, logs = await asyncio.to_thread(_run_cmd, pytest_cmd, target)
        if rc == 0 or rc == 5:
            break
        # On a missing-module failure, install it into the venv and retry.
        if py_exec == "python" or len(installed) >= _MAX_MODULE_INSTALLS:
            break
        m = _MISSING_MODULE_RE.search(logs)
        if not m:
            break
        mod = m.group(1).split(".")[0]
        pkg = _MODULE_TO_PIP.get(mod, mod)
        if pkg in installed:
            break  # already tried installing this — avoid a loop
        installed.append(pkg)
        logger.info("pytest: auto-installing missing module %r (pip %s)", mod, pkg)
        pip_rc, _ = await asyncio.to_thread(
            _run_cmd, [py_exec, "-m", "pip", "install", "-q", pkg], target, timeout=120
        )
        if pip_rc != 0:
            break  # can't install (e.g. name mismatch) → report the real failure

    dur = int((time.monotonic() - t0) * 1000)
    note = f"(auto-installed: {', '.join(installed)})\n" if installed else ""
    if rc == 5:
        return StepResult(
            status="skipped",
            logs=(note + logs) or "No tests collected by pytest.",
            duration_ms=dur,
            ai_reasoning="Skipped: pytest found no tests to run.",
        )
    status = "success" if rc == 0 else "failure"
    return StepResult(
        status=status,
        logs=note + logs,
        duration_ms=dur,
        ai_reasoning=f"pytest {'passed' if rc == 0 else 'failed'} (exit {rc}) in {dur}ms.",
    )


async def run_test(sandbox: Path) -> StepResult:
    """Run real tests: pytest (Python) or npm test (Node). Skip if none exist.

    Tests cannot be invented — if the project ships no test suite, this step is
    legitimately skipped rather than failed. ``build``/``lint`` still validate
    the code in that case.
    """
    t0 = time.monotonic()
    backend_dir = sandbox / "backend"
    frontend_dir = sandbox / "frontend"

    # 1) Python pytest — config file or test_*.py / *_test.py present
    py_target: Path | None = None
    if backend_dir.exists() and (
        (backend_dir / "pytest.ini").exists() or (backend_dir / "pyproject.toml").exists()
    ):
        py_target = backend_dir
    elif (sandbox / "pytest.ini").exists() or (sandbox / "pyproject.toml").exists():
        py_target = sandbox
    elif any(
        f.name.startswith("test_") or f.name.endswith("_test.py")
        for f in _iter_files(sandbox, (".py",))
    ):
        py_target = sandbox

    if py_target is not None:
        return await _run_pytest_step(py_target, t0)

    # 2) Node npm test — only when a real test script is declared
    for cand in (frontend_dir, sandbox):
        pkg = cand / "package.json"
        if not pkg.exists():
            continue
        scripts = _read_pkg_scripts(pkg)
        if not _has_real_script(scripts, "test"):
            break  # package.json present but no test script → skip below
        # Cross-ecosystem guard: a Node manifest whose test script is a Python
        # runner (e.g. "test": "pytest"). Do NOT npm-install — pytest and friends
        # are not npm packages. Run pytest instead so a Python project mislabelled
        # with a package.json still gets tested rather than crashing on ETARGET.
        if _is_python_test_script(scripts):
            return await _run_pytest_step(cand, t0)
        target = cand
        install_rc, install_logs = await asyncio.to_thread(_npm_install, target)
        if install_rc != 0:
            dur = int((time.monotonic() - t0) * 1000)
            return StepResult(
                status="failure",
                logs=install_logs,
                duration_ms=dur,
                ai_reasoning=f"npm install failed (exit {install_rc}).",
            )
        await asyncio.to_thread(_ensure_test_runner, target)

        # Remove duplicate Jest config files before running so Jest doesn't
        # bail out with "Multiple configurations found" (a common agent artefact
        # where the model wrote jest.config.js then jest.config.cjs as a fix).
        dedup_note = await asyncio.to_thread(_dedup_jest_configs, target)

        rc, logs = await asyncio.to_thread(
            _run_cmd, ["npm", "test", "--", "--watchAll=false", "--passWithNoTests"], target
        )
        dur = int((time.monotonic() - t0) * 1000)
        if dedup_note:
            logs = dedup_note + "\n\n" + logs
        status = "success" if rc == 0 else "failure"
        return StepResult(
            status=status,
            logs=logs,
            duration_ms=dur,
            ai_reasoning=f"npm test {'passed' if rc == 0 else 'failed'} (exit {rc}) in {dur}ms.",
        )

    dur = int((time.monotonic() - t0) * 1000)
    return StepResult(
        status="skipped",
        logs="No test suite detected (no pytest config/tests, no npm test script).",
        duration_ms=dur,
        ai_reasoning="Skipped: project ships no automated tests.",
    )


# ── Lint Runner ────────────────────────────────────────────────────────────────

async def run_lint(sandbox: Path) -> StepResult:
    """Lint every language present, falling back to syntax checks when no linter is configured."""
    t0 = time.monotonic()
    combined_logs: list[str] = []
    any_failure = False
    ran_something = False

    py_files = _iter_files(sandbox, (".py",))
    ts_files = _iter_files(sandbox, (".ts", ".tsx"))
    js_files = _iter_files(sandbox, (".js", ".jsx", ".mjs", ".cjs"))

    # Python: ruff, else py_compile syntax check
    if py_files:
        ran_something = True
        if shutil.which("ruff") or _module_available("ruff"):
            ruff_base = ["ruff"] if shutil.which("ruff") else ["python", "-m", "ruff"]
            # First auto-fix the trivial, safe issues AI code commonly has (unused
            # imports, import order). This keeps CI from failing on noise the linter
            # can resolve itself, and surfaces only the issues that need real changes.
            await asyncio.to_thread(_run_cmd, [*ruff_base, "check", ".", "--fix"], sandbox)
            # ruff >=0.5 removed `--output-format=text`; use `concise` (stable, parseable).
            rc, out = await asyncio.to_thread(
                _run_cmd, [*ruff_base, "check", ".", "--output-format=concise"], sandbox
            )
            combined_logs.append(f"=== ruff ===\n{out}")
            if rc != 0:
                any_failure = True
        else:
            rc, out = await _py_syntax_check(py_files)
            combined_logs.append(f"=== python syntax (ruff unavailable) ===\n{out}")
            if rc != 0:
                any_failure = True

    # JS/TS: eslint if configured, else node --check (JS) / tsc --noEmit (TS)
    frontend_dir = sandbox / "frontend"
    eslint_target = frontend_dir if frontend_dir.exists() else sandbox
    has_eslint_config = any(
        (eslint_target / name).exists()
        for name in (
            ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml",
            "eslint.config.js", "eslint.config.mjs", "eslint.config.ts",
        )
    )

    if has_eslint_config and shutil.which("npx"):
        ran_something = True
        if (eslint_target / "package.json").exists():
            await asyncio.to_thread(_npm_install, eslint_target)
        rc, out = await asyncio.to_thread(
            _run_cmd,
            ["npx", "eslint", ".", "--ext", ".ts,.tsx,.js,.jsx", "--max-warnings=0"],
            eslint_target, timeout=120,
        )
        combined_logs.append(f"=== eslint ===\n{out}")
        if rc != 0:
            any_failure = True
    else:
        # No eslint config → syntax/type fallbacks
        if js_files:
            ran_something = True
            rc, out = await _node_syntax_check(js_files)
            combined_logs.append(f"=== node --check (no eslint config) ===\n{out}")
            if rc != 0:
                any_failure = True
        if ts_files and shutil.which("npx"):
            ran_something = True
            tsc_cmd, tsc_cwd = _tsc_cmd(sandbox, ts_files)
            if (tsc_cwd / "package.json").exists():
                await asyncio.to_thread(_npm_install, tsc_cwd)
            rc, out = await asyncio.to_thread(_run_cmd, tsc_cmd, tsc_cwd, timeout=180)
            combined_logs.append(f"=== tsc --noEmit (no eslint config) ===\n{out}")
            if rc != 0:
                any_failure = True

    dur = int((time.monotonic() - t0) * 1000)
    if not ran_something:
        return StepResult(
            status="skipped",
            logs="No source files to lint.",
            duration_ms=dur,
            ai_reasoning="Skipped: no lintable source detected.",
        )

    status = "failure" if any_failure else "success"
    logs = "\n".join(combined_logs)[:_MAX_LOG_BYTES]
    return StepResult(
        status=status,
        logs=logs,
        duration_ms=dur,
        ai_reasoning=f"Lint {'found issues' if any_failure else 'passed clean'} in {dur}ms.",
    )


# ── Build Runner ───────────────────────────────────────────────────────────────

async def run_build(sandbox: Path) -> StepResult:
    """Validate that the project compiles: Docker → npm build → tsc → node → py_compile."""
    t0 = time.monotonic()

    # 1) Docker build (validates full stack)
    if (sandbox / "Dockerfile").exists() and shutil.which("docker"):
        rc, logs = await asyncio.to_thread(
            _run_cmd,
            ["docker", "build", "--no-cache", "-t", "neo-kanban-build-check", "."],
            sandbox, timeout=300,
        )
        return _build_result(rc, logs, t0, "Docker build")

    # 2) npm build — only if a build script is declared
    frontend_dir = sandbox / "frontend"
    pkg_json = (frontend_dir / "package.json") if frontend_dir.exists() else (sandbox / "package.json")
    if pkg_json.exists() and shutil.which("npm") and _has_real_script(_read_pkg_scripts(pkg_json), "build"):
        target = pkg_json.parent
        install_rc, install_logs = await asyncio.to_thread(_npm_install, target)
        if install_rc != 0:
            dur = int((time.monotonic() - t0) * 1000)
            return StepResult(
                status="failure", logs=install_logs, duration_ms=dur,
                ai_reasoning=f"npm install failed (exit {install_rc}).",
            )
        rc, logs = await asyncio.to_thread(_run_cmd, ["npm", "run", "build"], target, timeout=180)
        return _build_result(rc, logs, t0, "npm build")

    # 3) Loose TypeScript → tsc --noEmit compile check
    ts_files = _iter_files(sandbox, (".ts", ".tsx"))
    if ts_files and shutil.which("npx"):
        tsc_cmd, tsc_cwd = _tsc_cmd(sandbox, ts_files)
        if (tsc_cwd / "package.json").exists():
            await asyncio.to_thread(_npm_install, tsc_cwd)
        rc, logs = await asyncio.to_thread(_run_cmd, tsc_cmd, tsc_cwd, timeout=180)
        return _build_result(rc, logs, t0, "tsc compile check")

    # 4) Loose JavaScript → node --check syntax
    js_files = _iter_files(sandbox, (".js", ".jsx", ".mjs", ".cjs"))
    if js_files and shutil.which("node"):
        rc, out = await _node_syntax_check(js_files)
        return _build_result(rc, out, t0, "node syntax check")

    # 5) Python → py_compile
    py_files = _iter_files(sandbox, (".py",))
    if py_files:
        rc, out = await _py_syntax_check(py_files)
        return _build_result(rc, out, t0, "Python compile check")

    dur = int((time.monotonic() - t0) * 1000)
    return StepResult(
        status="skipped",
        logs="No buildable artifact detected (no Dockerfile/package.json/.ts/.js/.py).",
        duration_ms=dur,
        ai_reasoning="Skipped: no build target detected.",
    )


# ── Shared check helpers ─────────────────────────────────────────────────────

def _module_available(mod: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


async def _py_syntax_check(py_files: list[Path]) -> tuple[int, str]:
    """Compile each .py file; return (rc, log). rc != 0 if any file has a syntax error."""
    errors: list[str] = []
    for f in py_files[:100]:
        rc, out = await asyncio.to_thread(_run_cmd, ["python", "-m", "py_compile", str(f)], f.parent)
        if rc != 0:
            errors.append(f"{f.name}: {out.strip()}")
    if errors:
        return 1, "\n".join(errors)
    return 0, f"Syntax OK for {len(py_files[:100])} Python file(s)."


async def _node_syntax_check(js_files: list[Path]) -> tuple[int, str]:
    """node --check each JS file; return (rc, log). rc != 0 if any file has a syntax error."""
    errors: list[str] = []
    for f in js_files[:100]:
        rc, out = await asyncio.to_thread(_run_cmd, ["node", "--check", str(f)], f.parent)
        if rc != 0:
            errors.append(f"{f.name}: {out.strip()}")
    if errors:
        return 1, "\n".join(errors)
    return 0, f"Syntax OK for {len(js_files[:100])} JS file(s)."


def _build_result(rc: int, logs: str, t0: float, label: str) -> StepResult:
    dur = int((time.monotonic() - t0) * 1000)
    status = "success" if rc == 0 else "failure"
    return StepResult(
        status=status,
        logs=logs,
        duration_ms=dur,
        ai_reasoning=f"{label} {'succeeded' if rc == 0 else 'failed'} (exit {rc}) in {dur}ms.",
    )
