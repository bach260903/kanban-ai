"""Reviewer service — test runner detection, secret scanning, AI review, score calculation."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from app.llm.invoke_helpers import ainvoke_llm

# ---------------------------------------------------------------------------
# Test runner detection (T023)
# ---------------------------------------------------------------------------

_PYTEST_MARKERS = ["conftest.py", "pytest.ini", "pyproject.toml"]


def detect_test_runner(sandbox_path: str) -> str | None:
    """Detect which test runner the sandbox project uses.

    Args:
        sandbox_path: Absolute path to the sandbox root directory.

    Returns:
        ``"pytest"`` if Python test markers are found,
        ``"npm_test"`` if ``package.json`` has a ``scripts.test`` entry,
        or ``None`` if no runner is detected.
    """
    root = Path(sandbox_path)
    if any((root / marker).exists() for marker in _PYTEST_MARKERS):
        return "pytest"
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data: dict[str, Any] = json.loads(pkg.read_text(encoding="utf-8"))
            if data.get("scripts", {}).get("test"):
                return "npm_test"
        except (json.JSONDecodeError, OSError):
            pass
    return None


# ---------------------------------------------------------------------------
# Test execution (T024)
# ---------------------------------------------------------------------------

_TEST_CMDS: dict[str, list[str]] = {
    "pytest": ["pytest", "-v", "--tb=short"],
    "npm_test": ["npm", "test", "--", "--watchAll=false"],
}


def run_tests(
    runner: str,
    sandbox_path: str,
    timeout: int = 60,
) -> tuple[int, int, str | None]:
    """Run the project's test suite and return pass/fail counts.

    Args:
        runner: ``"pytest"`` or ``"npm_test"``. Unknown values fall back to
            pytest with a warning in ``error_text``.
        sandbox_path: Working directory for the subprocess.
        timeout: Maximum seconds before the process is killed.

    Returns:
        ``(pass_count, fail_count, error_text)``.
        *error_text* is ``None`` when the runner exited with rc == 0,
        otherwise the last 500 chars of combined stdout + stderr.
        Returns ``(0, 0, "<message>")`` on timeout or binary-not-found.
    """
    if runner not in _TEST_CMDS:
        return 0, 0, f"Unknown test runner: {runner!r}"
    cmd = _TEST_CMDS[runner]
    try:
        result = subprocess.run(
            cmd,
            cwd=sandbox_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        if runner == "pytest":
            m_pass = re.search(r"(\d+) passed", output)
            m_fail = re.search(r"(\d+) failed", output)
            passed = int(m_pass.group(1)) if m_pass else 0
            failed = int(m_fail.group(1)) if m_fail else 0
        else:
            # Jest: "Tests: 3 passed, 1 failed"
            m_pass = re.search(r"Tests:\s+(\d+) passed", output)
            m_fail = re.search(r"(\d+) failed", output)
            passed = int(m_pass.group(1)) if m_pass else 0
            failed = int(m_fail.group(1)) if m_fail else 0
        error_text: str | None = None if result.returncode == 0 else output[-500:]
        return passed, failed, error_text
    except subprocess.TimeoutExpired:
        return 0, 0, f"Test runner timed out after {timeout}s"
    except FileNotFoundError:
        binary = cmd[0]
        return 0, 0, f"Test runner binary not found: {binary!r} — ensure it is installed in the sandbox"


# ---------------------------------------------------------------------------
# Secret scanning (T025)
# ---------------------------------------------------------------------------

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{6,}["\']', "hardcoded password"),
    (r'(?i)(api_key|apikey|api-key)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "hardcoded API key"),
    (r'(?i)(secret|token)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "hardcoded secret/token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"(?i)bearer\s+[A-Za-z0-9\-_\.]{20,}", "Bearer token in code"),
]


def scan_secrets(diff_content: str) -> list[dict[str, Any]]:
    """Scan only added lines (starting with ``+``) in a unified diff for secrets.

    Tracks current file from ``+++ b/`` headers and line numbers from
    ``@@ +N @@`` hunks.

    Args:
        diff_content: Full unified diff string.

    Returns:
        List of ``{"file": str, "line": int, "pattern_name": str}`` findings.
    """
    findings: list[dict[str, Any]] = []
    current_file = "unknown"
    line_num = 0

    for line in diff_content.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            line_num = 0
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            line_num = int(m.group(1)) - 1 if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            line_num += 1
            for pattern, name in SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append(
                        {"file": current_file, "line": line_num, "pattern_name": name}
                    )

    return findings


# ---------------------------------------------------------------------------
# AI review (T026)
# ---------------------------------------------------------------------------

REVIEWER_PROMPT = """\
You are a senior code reviewer for an autonomous software factory. The diff below was written
by an AI coding agent and will be merged automatically once approved, so review it as the last
line of defense before code ships.

Review the diff against these criteria, in priority order:
1. CORRECTNESS — does the change do what the task intends? Logic errors, off-by-one, wrong
   conditions, unhandled cases, broken control flow.
2. BROKEN REFERENCES — imports/exports that won't resolve, calls to undefined symbols, files or
   modules referenced but not created, mismatched function signatures.
3. SECURITY — injection (SQL/command/XSS), missing input validation at trust boundaries, unsafe
   deserialization, path traversal, hardcoded credentials. (Obvious secrets are flagged
   separately — focus on logic-level security here.)
4. CONSTITUTION ADHERENCE — violations of the project standards below.
5. TESTS — missing coverage for new behavior, or tests that don't actually assert anything.
6. MAINTAINABILITY — only call out issues serious enough to matter; do not nitpick style the
   linter already handles.

Project constitution (coding standards):
{constitution}

Git diff:
{diff}

Return ONLY valid JSON with this exact shape:
{{
  "suggestion": "approve",
  "comments": [
    {{"file_path": "path/to/file.py", "line_number": 42, "content": "explanation", "severity": "info"}}
  ]
}}

Rules:
- "suggestion": "approve" only if there are no "error"-severity issues; otherwise "needs_changes".
- "severity": "error" (blocks merge: bugs, broken refs, security) | "warning" (should fix) |
  "info" (minor/optional).
- Each comment must point to a real file_path and line_number from the diff and explain BOTH the
  problem and the concrete fix — actionable, not vague.
- Limit to the 10 most important comments. Be concise. Do not invent issues to fill the list.\
"""


_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _extract_json(text: str) -> str:
    """Strip optional markdown code-fence wrapping from an LLM response.

    LLMs commonly wrap JSON in ```json ... ``` blocks. This helper extracts
    the inner content so ``json.loads`` can handle it.
    """
    m = _MARKDOWN_JSON_RE.search(text)
    return m.group(1) if m else text.strip()


async def ai_review_diff(
    diff: str,
    constitution: str,
    llm: Any,
) -> tuple[str, list[dict[str, Any]]]:
    """Ask the LLM to review a diff and return (suggestion, comments).

    Args:
        diff: Unified diff string (truncated to 6 000 chars internally).
        constitution: Project constitution text (truncated to 2 000 chars).
        llm: LangChain chat model instance.

    Returns:
        ``(suggestion, comments)`` where ``suggestion`` is ``"approve"`` or
        ``"needs_changes"`` and ``comments`` is a list of comment dicts.
        Falls back to ``("needs_changes", [])`` on any parse or LLM error
        so that the reviewer node never crashes the task pipeline.
    """
    prompt = REVIEWER_PROMPT.format(
        constitution=constitution[:2000],
        diff=diff[:6000],
    )
    try:
        response = await ainvoke_llm(llm, prompt)
        raw = getattr(response, "content", "") or ""
        data: dict[str, Any] = json.loads(_extract_json(raw))
        suggestion: str = data.get("suggestion", "needs_changes")
        comments: list[dict[str, Any]] = data.get("comments", [])
        return suggestion, comments
    except Exception:  # noqa: BLE001 — any LLM/network/parse error must not crash the pipeline
        return "needs_changes", []


# ---------------------------------------------------------------------------
# Score calculation (T027)
# ---------------------------------------------------------------------------

def calculate_score(
    test_pass: int,
    test_fail: int,
    secret_count: int,
    suggestion: str,
) -> int:
    """Compute a 0–100 review quality score (slightly lenient, still discriminating).

    Breakdown:
    - **Test score** (40 pts): ``floor(pass / total * 40)`` when tests ran; **18 pts
      baseline** when no tests are detected (untested ≠ broken, so partial credit
      rather than zero — but well below a tested project).
    - **Secret score** (30 pts): 30 − 15 × secrets_found (min 0). Kept strict —
      hardcoded secrets are a real security problem.
    - **AI score** (30 pts): 30 if ``"approve"``, **14 if ``"needs_changes"``**
      (penalised but not crushed).

    Rationale: the old scoring was harsh — untested code scored 0 on tests and a
    "needs_changes" verdict scored only 5, so reasonable work landed in the 40s–60s.
    This version is a bit more generous while still ranking: tested+approved+clean =
    100; untested+approved+clean ≈ 78; tested+needs_changes+clean ≈ 84; a leaked
    secret still drops the score sharply.

    Args:
        test_pass: Number of passing tests.
        test_fail: Number of failing tests.
        secret_count: Number of secret findings from :func:`scan_secrets`.
        suggestion: ``"approve"`` or ``"needs_changes"``.

    Returns:
        Integer score clamped to [0, 100].
    """
    total = test_pass + test_fail
    # No tests → partial baseline credit (untested isn't a failure); tests present →
    # proportional credit. Failing tests pull this down naturally.
    test_score = 18 if total == 0 else int((test_pass / total) * 40)
    secret_score = max(0, 30 - secret_count * 15)
    ai_score = 30 if suggestion == "approve" else 14
    return max(0, min(100, test_score + secret_score + ai_score))
