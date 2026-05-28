"""Failure analyst node — AI-powered CI step failure diagnosis.

Given a failed step's logs, key, and sandbox context, this node:
1. Builds a structured analysis prompt
2. Calls the review/architect LLM for JSON output
3. Returns a FailureAnalysis dataclass with root_cause, confidence, fix_strategy,
   is_auto_fixable, and safety flags.

Design:
- Pure function: no DB access, no side effects.
- Uses existing LLM factory (same provider as reviewer agent).
- Falls back to a heuristic analysis if LLM is unavailable.
- All dangerous fixes are flagged for human approval.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# ── Safety: patterns that ALWAYS require human approval ──────────────────────

_APPROVAL_KEYWORDS = [
    "auth",
    "secret",
    "password",
    "token",
    "credential",
    "api.key",
    "private.key",
    "schema.migrat",
    "database.migrat",
    "drop.table",
    "delete.table",
    "upgrade.depend",
    "dependency.upgrade",
    "security",
    "certificate",
    "ssl",
    "tls",
    "firewall",
    "permission",
    "role",
    "rbac",
]

_CRITICAL_PATH_FRAGMENTS = [
    ".env",
    "settings.py",
    "config.py",
    "secret",
    "credential",
    "alembic/versions",
    "migrations/",
    ".pem",
    ".key",
    ".crt",
]

# Log patterns → likely root cause (heuristic fallback)
_HEURISTIC_PATTERNS: list[tuple[re.Pattern[str], str, str, bool]] = [
    (re.compile(r"ModuleNotFoundError: No module named '([^']+)'"), "Missing Python module: {0}", "Install missing package in requirements", True),
    (re.compile(r"ImportError: cannot import name '([^']+)'"), "Import error: cannot import '{0}'", "Fix import path or install correct package version", True),
    (re.compile(r"SyntaxError:"), "Python syntax error in source file", "Fix the syntax error indicated in the logs", True),
    (re.compile(r"FAILED.*AssertionError"), "Test assertion failure", "Fix the failing test or the code under test", False),
    (re.compile(r"npm ERR! missing.*'([^']+)'"), "Missing npm package: {0}", "Run npm install or add missing dependency to package.json", True),
    (re.compile(r"Cannot find module '([^']+)'"), "Missing Node module: {0}", "Add {0} to package.json dependencies and run npm install", True),
    (re.compile(r"error TS\d+:"), "TypeScript compilation error", "Fix TypeScript type errors", True),
    (re.compile(r"error:\s+\[E\d+\]"), "Rust compilation error", "Fix Rust compiler errors", False),
    (re.compile(r"docker.*not found|Cannot connect to the Docker daemon"), "Docker not available", "Install Docker or use a non-Docker build target", False),
    (re.compile(r"permission denied|Permission denied"), "Permission error accessing files", "Fix file permissions in the sandbox", False),
    (re.compile(r"pytest.*collected 0 items"), "No tests collected by pytest", "Check test file naming (test_*.py) and conftest.py", True),
    (re.compile(r"Address already in use"), "Port conflict during test", "Use random port or mock the server in tests", True),
    (re.compile(r"Connection refused|connection refused"), "Service connection refused during test", "Mock external services or start required services", True),
    (re.compile(r"ruff.*error|ESLint.*error"), "Lint errors found", "Fix the lint errors highlighted in the logs", True),
    (re.compile(r"exit code 137|OOMKilled|out of memory"), "Process killed (out of memory)", "Reduce memory usage or increase limits", False),
]


@dataclass
class FailureAnalysis:
    """Result of analyzing a failed pipeline step."""

    root_cause: str
    confidence: float            # 0.0–1.0
    fix_strategy: str
    is_auto_fixable: bool
    human_approval_required: bool
    risk_level: str              # 'low' | 'medium' | 'high'
    fix_files: list[dict[str, str]] = field(default_factory=list)
    ai_raw_response: str = ""
    ai_prompt_snippet: str = ""
    via_llm: bool = False        # True if LLM was used, False = heuristic


# ── Public entry point ────────────────────────────────────────────────────────

async def analyze_step_failure(
    *,
    step_key: str,
    logs: str,
    sandbox: Path | None = None,
) -> FailureAnalysis:
    """Analyze a failed step and return a structured FailureAnalysis.

    Tries LLM first; falls back to heuristics if LLM is not configured or fails.
    """
    from app.llm.factory import architect_llm_configured, create_architect_llm

    if architect_llm_configured():
        try:
            return await _llm_analysis(step_key=step_key, logs=logs, sandbox=sandbox)
        except Exception as exc:
            logger.warning(
                "failure_analyst: LLM analysis failed (%s), falling back to heuristics", exc
            )

    return _heuristic_analysis(step_key=step_key, logs=logs)


# ── LLM analysis ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert CI/CD failure analyst embedded in an AI-native pipeline system.
Your job is to diagnose why a pipeline step failed, suggest a precise fix,
and decide if the fix can be applied automatically (safely, without human review).

SAFETY RULES — if ANY of these apply, set human_approval_required=true:
- Fix involves auth, secrets, passwords, tokens, API keys, credentials
- Fix involves database/schema migrations
- Fix involves dependency version upgrades (major versions)
- Fix involves security config, SSL/TLS, firewall, RBAC
- Fix would delete or overwrite critical config files (.env, secrets.*)
- Risk level is high

You respond ONLY with a valid JSON object, no markdown fences, no extra text.
"""

_HUMAN_PROMPT_TEMPLATE = """\
A CI/CD pipeline step failed. Analyze and respond with JSON.

Step: {step_key}
Sandbox path hint: {sandbox_hint}

=== FAILURE LOGS (last 4000 chars) ===
{logs}
=== END LOGS ===

Respond with EXACTLY this JSON structure:
{{
  "root_cause": "...",
  "confidence": 0.0,
  "fix_strategy": "...",
  "is_auto_fixable": false,
  "human_approval_required": false,
  "risk_level": "low",
  "fix_files": [
    {{"path": "relative/path", "content": "full file content here"}}
  ]
}}

Rules:
- root_cause: one clear sentence describing WHY it failed
- confidence: 0.0-1.0 (how certain you are)
- fix_strategy: one-paragraph description of the fix
- is_auto_fixable: true only if fix is safe, low-risk, and you can provide exact file content
- fix_files: list of files to create/overwrite to fix the issue (only when is_auto_fixable=true)
  * Each entry: {{"path": "relative/path/to/file", "content": "complete file content"}}
  * Only include files you are CONFIDENT about
  * Limit to 3 files maximum
- human_approval_required: true if fix touches auth/secrets/migrations/security
- risk_level: "low" | "medium" | "high"
"""


async def _llm_analysis(
    *,
    step_key: str,
    logs: str,
    sandbox: Path | None,
) -> FailureAnalysis:
    from app.llm.factory import create_architect_llm
    from app.llm.invoke_helpers import ainvoke_llm

    log_snippet = logs[-4000:] if len(logs) > 4000 else logs
    sandbox_hint = str(sandbox) if sandbox else "(unknown)"

    prompt = _HUMAN_PROMPT_TEMPLATE.format(
        step_key=step_key,
        sandbox_hint=sandbox_hint,
        logs=log_snippet,
    )

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    llm = create_architect_llm(temperature=0.1)
    t0 = time.monotonic()
    response = await ainvoke_llm(llm, messages)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    logger.debug("failure_analyst LLM returned in %dms", elapsed_ms)

    raw_text: str = str(getattr(response, "content", response))
    parsed = _parse_llm_json(raw_text)

    # Safety override: always enforce approval for dangerous fix strategies
    fix_strategy_lower = parsed.get("fix_strategy", "").lower()
    root_cause_lower = parsed.get("root_cause", "").lower()
    combined_lower = fix_strategy_lower + " " + root_cause_lower

    human_required = bool(parsed.get("human_approval_required", False))
    for kw in _APPROVAL_KEYWORDS:
        if kw in combined_lower:
            human_required = True
            break

    # Safety override: if fix_files touch critical paths → require approval
    fix_files: list[dict[str, str]] = parsed.get("fix_files", [])
    for ff in fix_files:
        path_lower = str(ff.get("path", "")).lower()
        for frag in _CRITICAL_PATH_FRAGMENTS:
            if frag in path_lower:
                human_required = True
                break

    # If human approval required, don't auto-apply
    is_fixable = bool(parsed.get("is_auto_fixable", False)) and not human_required
    if not is_fixable:
        fix_files = []

    return FailureAnalysis(
        root_cause=parsed.get("root_cause", "Unknown failure"),
        confidence=float(parsed.get("confidence", 0.5)),
        fix_strategy=parsed.get("fix_strategy", "Manual investigation required"),
        is_auto_fixable=is_fixable,
        human_approval_required=human_required,
        risk_level=parsed.get("risk_level", "medium"),
        fix_files=fix_files,
        ai_raw_response=raw_text[:8000],
        ai_prompt_snippet=prompt[:2000],
        via_llm=True,
    )


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM output, stripping markdown fences."""
    # Strip markdown code fences
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # Try to find first {...} block
    match = re.search(r"\{[\s\S]*\}", clean)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("failure_analyst: could not parse LLM JSON: %s", text[:200])
    return {}


# ── Heuristic fallback ────────────────────────────────────────────────────────

def _heuristic_analysis(*, step_key: str, logs: str) -> FailureAnalysis:
    """Rule-based failure analysis when LLM is unavailable."""
    for pattern, cause_template, fix, auto_fixable in _HEURISTIC_PATTERNS:
        m = pattern.search(logs)
        if m:
            groups = m.groups()
            root_cause = cause_template.format(*groups) if groups else cause_template
            fix_strategy = fix.format(*groups) if groups else fix
            # Safety: never auto-fix if root_cause OR fix_strategy mentions approval keywords
            combined = (root_cause + " " + fix_strategy).lower()
            human_required = any(kw in combined for kw in _APPROVAL_KEYWORDS)
            return FailureAnalysis(
                root_cause=root_cause,
                confidence=0.7,
                fix_strategy=fix_strategy,
                is_auto_fixable=auto_fixable and not human_required,
                human_approval_required=human_required,
                risk_level="low" if auto_fixable else "medium",
                via_llm=False,
            )

    # Generic fallback
    last_lines = "\n".join(logs.strip().splitlines()[-10:])
    return FailureAnalysis(
        root_cause=f"Step '{step_key}' failed — see logs for details",
        confidence=0.3,
        fix_strategy=(
            f"Manually inspect the {step_key} step logs. "
            f"Last lines:\n{last_lines}"
        ),
        is_auto_fixable=False,
        human_approval_required=False,
        risk_level="medium",
        via_llm=False,
    )
