"""Failure analysis service — persists AI analysis and orchestrates auto-fix patches.

This is the DB-aware layer that sits between the executor and the analyst node.
It:
  1. Calls the analyst node to get AI analysis
  2. Persists the analysis to step_failure_analyses
  3. Applies auto-fix patches to the sandbox (if safe and authorized)
  4. Returns enough info for the executor to decide whether to retry
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.step_failure_analysis import StepFailureAnalysis
from app.models.pipeline_step import PipelineStep

logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 500_000  # 500 KB max per patched file
_SAFE_EXTENSIONS = {
    ".py", ".txt", ".md", ".toml", ".cfg", ".ini", ".yaml", ".yml",
    ".json", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".env.example",
    ".sh", ".bat", ".env.test", ".env.ci",
}
# Extensions that are NEVER auto-patched
_FORBIDDEN_EXTENSIONS = {
    ".pem", ".key", ".crt", ".p12", ".pfx", ".der",
    ".exe", ".dll", ".so", ".dylib",
}
# File name fragments that are NEVER auto-patched
_FORBIDDEN_NAME_FRAGMENTS = [
    ".env",
    "secrets",
    "credential",
    "private_key",
    "id_rsa",
    "id_ed25519",
]


@dataclass
class AnalysisResult:
    analysis: StepFailureAnalysis
    should_retry: bool
    retry_reason: str


# ── Main entry point ──────────────────────────────────────────────────────────

async def analyze_and_fix(
    session: AsyncSession,
    *,
    step: PipelineStep,
    sandbox: Path,
) -> AnalysisResult:
    """Analyze a failed step, persist analysis, optionally apply patch.

    Returns an AnalysisResult indicating whether a retry should be triggered.
    """
    from app.agent.nodes.failure_analyst_node import analyze_step_failure

    # 1. Run AI analysis
    logs = step.logs or ""
    fa_result = await analyze_step_failure(
        step_key=step.step_key,
        logs=logs,
        sandbox=sandbox,
    )

    # 2. Persist analysis to DB
    row = StepFailureAnalysis(
        step_id=step.id,
        run_id=step.run_id,
        root_cause=fa_result.root_cause,
        confidence=fa_result.confidence,
        fix_strategy=fa_result.fix_strategy,
        is_auto_fixable=fa_result.is_auto_fixable,
        human_approval_required=fa_result.human_approval_required,
        risk_level=fa_result.risk_level,
        ai_prompt_snippet=fa_result.ai_prompt_snippet or "",
        ai_raw_response=fa_result.ai_raw_response or "",
        patch_applied=False,
        retry_triggered=False,
    )
    session.add(row)
    await session.flush()  # get row.id

    logger.info(
        "failure_analysis: step=%s run=%s root_cause=%r fixable=%s via_llm=%s",
        step.step_key,
        step.run_id,
        fa_result.root_cause[:80],
        fa_result.is_auto_fixable,
        fa_result.via_llm,
    )

    # 3. Auto-fix: only if safe and has file changes
    patch_applied = False
    patch_summary = ""
    if fa_result.is_auto_fixable and fa_result.fix_files and not fa_result.human_approval_required:
        patch_applied, patch_summary = await _apply_patch(
            sandbox=sandbox,
            fix_files=fa_result.fix_files,
        )
        row.patch_applied = patch_applied
        row.patch_summary = patch_summary
        await session.flush()

    # 4. Decide retry
    should_retry = patch_applied or (
        fa_result.is_auto_fixable
        and not fa_result.human_approval_required
        and step.attempt < 2  # max 1 auto-retry per step
    )
    retry_reason = ""
    if should_retry:
        retry_reason = (
            f"AI fix applied ({patch_summary}). Retrying step."
            if patch_applied
            else f"AI determined step is auto-fixable: {fa_result.fix_strategy[:200]}"
        )
        row.retry_triggered = True
        row.retry_attempt = step.attempt + 1

    await session.flush()

    return AnalysisResult(
        analysis=row,
        should_retry=should_retry,
        retry_reason=retry_reason,
    )


async def get_analyses_for_run(
    session: AsyncSession,
    run_id: UUID,
) -> list[StepFailureAnalysis]:
    """Return all failure analyses for a pipeline run, ordered by creation time."""
    rows = await session.scalars(
        select(StepFailureAnalysis)
        .where(StepFailureAnalysis.run_id == run_id)
        .order_by(StepFailureAnalysis.created_at)
    )
    return list(rows)


async def get_analysis_for_step(
    session: AsyncSession,
    step_id: UUID,
) -> StepFailureAnalysis | None:
    """Return the most recent failure analysis for a pipeline step."""
    return await session.scalar(
        select(StepFailureAnalysis)
        .where(StepFailureAnalysis.step_id == step_id)
        .order_by(StepFailureAnalysis.created_at.desc())
        .limit(1)
    )


# ── Patch application ─────────────────────────────────────────────────────────

async def _apply_patch(
    sandbox: Path,
    fix_files: list[dict[str, str]],
) -> tuple[bool, str]:
    """Write AI-generated file changes to the sandbox (sync → thread).

    Returns (success: bool, summary: str).
    """
    return await asyncio.to_thread(_apply_patch_sync, sandbox, fix_files)


def _apply_patch_sync(
    sandbox: Path,
    fix_files: list[dict[str, str]],
) -> tuple[bool, str]:
    written: list[str] = []
    errors: list[str] = []

    for entry in fix_files[:3]:  # hard cap at 3 files
        rel_path = str(entry.get("path", "")).strip().replace("\\", "/").lstrip("/")
        content = str(entry.get("content", ""))

        if not rel_path:
            errors.append("Skipped: empty path in fix_files entry")
            continue

        # Safety: validate extension
        suffix = Path(rel_path).suffix.lower()
        if suffix in _FORBIDDEN_EXTENSIONS:
            errors.append(f"Skipped: forbidden extension {suffix} in {rel_path}")
            logger.warning("patch_apply: blocked forbidden extension %s", rel_path)
            continue

        # Safety: validate name fragments
        rel_lower = rel_path.lower()
        if any(frag in rel_lower for frag in _FORBIDDEN_NAME_FRAGMENTS):
            errors.append(f"Skipped: forbidden path fragment in {rel_path}")
            logger.warning("patch_apply: blocked sensitive path %s", rel_path)
            continue

        # Safety: path traversal guard
        target = (sandbox / rel_path).resolve()
        try:
            target.relative_to(sandbox.resolve())
        except ValueError:
            errors.append(f"Skipped: path escapes sandbox — {rel_path}")
            logger.warning("patch_apply: sandbox escape attempt %s", rel_path)
            continue

        # Size guard
        if len(content.encode()) > _MAX_FILE_BYTES:
            errors.append(f"Skipped: content too large for {rel_path}")
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(rel_path)
            logger.info("patch_apply: wrote %s (%d bytes)", rel_path, len(content))
        except Exception as exc:
            errors.append(f"Write failed for {rel_path}: {exc}")
            logger.warning("patch_apply: write failed for %s — %s", rel_path, exc)

    if written:
        summary = f"Patched {len(written)} file(s): {', '.join(written)}"
        if errors:
            summary += f" (skipped: {'; '.join(errors)})"
        return True, summary

    reason = "; ".join(errors) if errors else "No changes applied"
    return False, reason
