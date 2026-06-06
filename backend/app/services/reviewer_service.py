"""Reviewer service — test runner detection, secret scanning, AI review, score calculation."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, SystemMessage

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

_REVIEWER_SYSTEM = """\
You are a senior code reviewer for an autonomous software factory. The diff was written
by an AI coding agent and will be merged automatically once approved — you are the last
line of defense before code ships.

Review criteria (priority order):
1. CORRECTNESS — logic errors, off-by-one, wrong conditions, unhandled cases, broken control flow.
2. BROKEN REFERENCES — imports/exports that won't resolve, calls to undefined symbols, files
   referenced but not created, mismatched function signatures.
3. SECURITY — SQL/command/XSS injection, missing input validation, unsafe deserialization,
   path traversal, hardcoded credentials.
4. CONSTITUTION ADHERENCE — violations of the project coding standards provided.
5. TESTS — missing coverage for new behaviour, or tests that assert nothing meaningful.
6. MAINTAINABILITY — only issues serious enough to matter; ignore style the linter handles.

Return ONLY valid JSON — no prose, no markdown fences, no explanation outside the JSON:
{
  "suggestion": "approve",
  "comments": [
    {"file_path": "path/to/file.py", "line_number": 42, "content": "explanation", "severity": "info"}
  ]
}

Rules:
- "suggestion": "approve" only when there are zero "error"-severity issues; else "needs_changes".
- "severity": "error" (blocks merge) | "warning" (should fix) | "info" (optional).
- Each comment must cite a real file_path + line_number from the diff and explain the problem
  AND the concrete fix. Be actionable, not vague.
- Limit to the 10 most important comments.\
"""

_REVIEWER_HUMAN = """\
Project constitution (coding standards):
{constitution}

Git diff to review:
{diff}\
"""


_MARKDOWN_JSON_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_THINK_TAG_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.IGNORECASE)


def _extract_json(text: str) -> str:
    """Extract JSON from an LLM response, handling code fences and thinking tags.

    Handles three common LLM output formats:
    1. Plain JSON
    2. JSON wrapped in ```json ... ``` code fences
    3. Thinking-model output with <think>...</think> prefix (Qwen3, DeepSeek-R1, etc.)
    """
    # Strip <think>...</think> blocks produced by reasoning/thinking models
    text = _THINK_TAG_RE.sub("", text).strip()
    # Try markdown code fence first
    m = _MARKDOWN_JSON_RE.search(text)
    if m:
        return m.group(1)
    # Try to find a raw JSON object in the remaining text
    m2 = _JSON_OBJECT_RE.search(text)
    if m2:
        return m2.group(0)
    return text.strip()


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
    messages = [
        SystemMessage(content=_REVIEWER_SYSTEM),
        HumanMessage(content=_REVIEWER_HUMAN.format(
            constitution=constitution[:2000],
            diff=diff[:6000],
        )),
    ]
    try:
        response = await ainvoke_llm(llm, messages)
        raw = getattr(response, "content", "") or ""
        data: dict[str, Any] = json.loads(_extract_json(raw))
        suggestion: str = data.get("suggestion", "needs_changes")
        comments: list[dict[str, Any]] = data.get("comments", [])
        return suggestion, comments
    except Exception as exc:  # noqa: BLE001 — any LLM/network/parse error must not crash the pipeline
        logger.warning("ai_review_diff failed (%s: %s)", type(exc).__name__, exc)
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
