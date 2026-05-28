"""Sequential MVP pipeline executor — Phase 3 self-healing.

Execution order: test → lint → build → preview_deploy

Phase 3 additions:
  - On step failure: call failure_analyst_node (AI root cause)
  - If auto-fixable + safe: apply patch, retry step once
  - Emit new SSE events: step_analysis_started, step_analysis_complete,
    step_fix_started, step_fix_complete, step_retry_started, approval_required
  - Max 1 auto-retry per step (step.attempt tracks retries)

Architecture designed for DAG upgrade:
  Replace STEP_ORDER with a DAG; replace loop with topological-sort + asyncio.gather.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.deployment import Deployment, DeploymentStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_step import PipelineStep, PipelineStepStatus
from app.pipeline import event_bus
from app.pipeline import step_runner

logger = logging.getLogger(__name__)

# Step execution order — sequential for MVP, DAG-compatible by design
STEP_ORDER = ["test", "lint", "build", "preview_deploy"]

_CI_RUNNERS = {
    "test":  step_runner.run_test,
    "lint":  step_runner.run_lint,
    "build": step_runner.run_build,
}

# Max automatic retries per step (after AI analysis + patch)
_MAX_AUTO_RETRIES = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Main executor ─────────────────────────────────────────────────────────────

async def execute_pipeline(run_id: UUID, sandbox: Path) -> None:
    """Main pipeline entry point — runs in a background asyncio task.

    Opens its own DB session (not shared with HTTP request) so the HTTP
    response is not blocked and the session is properly scoped to the task.
    """
    async with async_session_maker() as session:
        run = await session.get(PipelineRun, run_id)
        if run is None:
            logger.error("execute_pipeline: PipelineRun %s not found", run_id)
            return

        run.status = PipelineRunStatus.RUNNING
        run.started_at = _now()
        await session.commit()

        await event_bus.emit(str(run_id), "pipeline_started", {
            "run_id": str(run_id),
            "project_id": str(run.project_id),
        })

        # Load GitHub config once — used for status posts throughout
        from app.models.github_config import GitHubConfig
        gh_config = await session.scalar(
            select(GitHubConfig).where(
                GitHubConfig.project_id == run.project_id,
                GitHubConfig.enabled.is_(True),
            )
        )
        if gh_config and run.commit_sha:
            from app.services import github_service
            try:
                await github_service.post_pipeline_status(
                    gh_config, run.commit_sha,
                    state="pending",
                    description="Neo-Kanban pipeline running…",
                )
            except Exception:
                logger.debug("GitHub status post failed (non-fatal)", exc_info=True)

        overall_ok = True

        for step_key in STEP_ORDER:
            step = await _get_or_create_step(session, run_id, step_key)

            # ── Execute step (with AI-heal retry loop) ─────────────────────
            step_ok = await _execute_step_with_healing(
                session=session,
                run=run,
                step=step,
                step_key=step_key,
                sandbox=sandbox,
            )

            if not step_ok:
                overall_ok = False
                logger.warning("Pipeline %s failed at step '%s'", run_id, step_key)
                break  # stop pipeline on unrecoverable failure

        # ── Finalise run ──────────────────────────────────────────────────────
        final_status = PipelineRunStatus.SUCCESS if overall_ok else PipelineRunStatus.FAILURE
        run.status = final_status
        run.completed_at = _now()
        run.ai_summary = _build_summary(run, overall_ok)
        await session.commit()

        # Post final GitHub pipeline status
        if gh_config and run.commit_sha:
            from app.services import github_service
            try:
                await github_service.post_pipeline_status(
                    gh_config, run.commit_sha,
                    state="success" if overall_ok else "failure",
                    description=run.ai_summary or ("Pipeline passed" if overall_ok else "Pipeline failed"),
                )
            except Exception:
                logger.debug("GitHub final status post failed (non-fatal)", exc_info=True)

        # Post GitHub deployment status if we have a preview URL
        deployment = await session.scalar(
            select(Deployment).where(Deployment.run_id == run.id)
        )
        if deployment and deployment.preview_url and gh_config and run.commit_sha:
            from app.services import github_service
            try:
                await github_service.post_deployment_status(
                    gh_config,
                    commit_sha=run.commit_sha,
                    environment="preview",
                    state="success",
                    preview_url=deployment.preview_url,
                    description=f"Preview deployed: {deployment.preview_url}",
                )
            except Exception:
                logger.debug("GitHub deployment status post failed (non-fatal)", exc_info=True)

        event_type = "pipeline_completed" if overall_ok else "pipeline_failed"
        final_event: dict = {
            "run_id": str(run_id),
            "status": final_status,
            "ai_summary": run.ai_summary or "",
        }
        if deployment and deployment.preview_url:
            final_event["preview_url"] = deployment.preview_url

        await event_bus.emit(str(run_id), event_type, final_event)
        await event_bus.close_run(str(run_id))
        logger.info("Pipeline run %s finished status=%s", run_id, final_status)


# ── Step execution with AI self-healing ──────────────────────────────────────

async def _execute_step_with_healing(
    *,
    session: AsyncSession,
    run: PipelineRun,
    step: PipelineStep,
    step_key: str,
    sandbox: Path,
) -> bool:
    """Run a step, and if it fails attempt AI-driven recovery.

    Returns True if the step ultimately succeeded (or was skipped).
    Returns False if it failed and could not be recovered.
    """
    run_id = run.id

    # ── First attempt ─────────────────────────────────────────────────────────
    result_status, logs, duration_ms, ai_reasoning, preview_url = \
        await _run_single_step(session, run, step, step_key, sandbox)

    if result_status != "failure":
        return result_status != "failure"  # success or skipped

    # ── Step failed — try AI self-healing ─────────────────────────────────────
    if step.attempt >= _MAX_AUTO_RETRIES + 1:
        logger.info("Step %s already at max retries (%d), skipping analysis", step_key, step.attempt)
        return False

    # Emit: AI analysis starting
    await event_bus.emit(str(run_id), "step_analysis_started", {
        "run_id": str(run_id),
        "step_key": step_key,
        "step_id": str(step.id),
    })

    # Run analysis + optional patch
    try:
        from app.services import failure_analysis_service
        analysis_result = await failure_analysis_service.analyze_and_fix(
            session,
            step=step,
            sandbox=sandbox,
        )
        await session.commit()
    except Exception as exc:
        logger.exception("failure_analysis failed for step %s: %s", step_key, exc)
        # Emit analysis complete with minimal data, no retry
        await event_bus.emit(str(run_id), "step_analysis_complete", {
            "run_id": str(run_id),
            "step_key": step_key,
            "step_id": str(step.id),
            "root_cause": f"Analysis failed: {exc}",
            "confidence": 0.0,
            "fix_strategy": "Manual investigation required",
            "is_auto_fixable": False,
            "human_approval_required": False,
        })
        return False

    analysis = analysis_result.analysis

    # Emit: analysis complete
    analysis_event: dict = {
        "run_id": str(run_id),
        "step_key": step_key,
        "step_id": str(step.id),
        "analysis_id": str(analysis.id),
        "root_cause": analysis.root_cause,
        "confidence": analysis.confidence,
        "fix_strategy": analysis.fix_strategy,
        "is_auto_fixable": analysis.is_auto_fixable,
        "human_approval_required": analysis.human_approval_required,
        "risk_level": analysis.risk_level,
    }
    await event_bus.emit(str(run_id), "step_analysis_complete", analysis_event)

    # Human approval required → cannot auto-fix
    if analysis.human_approval_required:
        await event_bus.emit(str(run_id), "approval_required", {
            "run_id": str(run_id),
            "step_key": step_key,
            "step_id": str(step.id),
            "analysis_id": str(analysis.id),
            "root_cause": analysis.root_cause,
            "fix_strategy": analysis.fix_strategy,
        })
        return False

    # Not retrying → pipeline fails
    if not analysis_result.should_retry:
        return False

    # ── Patch was applied, now retry the step ────────────────────────────────
    if analysis.patch_applied:
        await event_bus.emit(str(run_id), "step_fix_complete", {
            "run_id": str(run_id),
            "step_key": step_key,
            "step_id": str(step.id),
            "analysis_id": str(analysis.id),
            "patch_summary": analysis.patch_summary or "",
            "success": True,
        })

    # Increment attempt counter and retry
    step.attempt += 1
    step.status = PipelineStepStatus.RUNNING
    step.started_at = _now()
    step.completed_at = None
    await session.commit()

    await event_bus.emit(str(run_id), "step_retry_started", {
        "run_id": str(run_id),
        "step_key": step_key,
        "step_id": str(step.id),
        "attempt": step.attempt,
        "reason": analysis_result.retry_reason,
    })

    # Execute the retry
    retry_status, retry_logs, retry_duration, retry_reasoning, retry_preview = \
        await _run_single_step(session, run, step, step_key, sandbox, emit_events=False)

    # Update step with retry result (overwriting the failure)
    step.status = PipelineStepStatus(retry_status)
    step.logs = retry_logs
    step.duration_ms = retry_duration
    step.ai_reasoning = f"[Retry {step.attempt}] {retry_reasoning}"
    step.completed_at = _now()
    await session.commit()

    retry_ok = retry_status == "success"
    logger.info(
        "Step %s retry (attempt=%d) result=%s",
        step_key, step.attempt, retry_status,
    )

    # Emit updated step_completed for the retry
    await event_bus.emit(str(run_id), "step_completed", {
        "run_id": str(run_id),
        "step_key": step_key,
        "step_id": str(step.id),
        "status": retry_status,
        "duration_ms": retry_duration,
        "ai_reasoning": step.ai_reasoning,
        "attempt": step.attempt,
        "was_retry": True,
    })

    return retry_ok


# ── Single step execution ─────────────────────────────────────────────────────

async def _run_single_step(
    session: AsyncSession,
    run: PipelineRun,
    step: PipelineStep,
    step_key: str,
    sandbox: Path,
    *,
    emit_events: bool = True,
) -> tuple[str, str, int, str, str | None]:
    """Execute one step and persist the result.

    Returns (status, logs, duration_ms, ai_reasoning, preview_url|None).
    """
    run_id = run.id

    if emit_events:
        step.status = PipelineStepStatus.RUNNING
        step.started_at = _now()
        await session.commit()

        await event_bus.emit(str(run_id), "step_started", {
            "run_id": str(run_id),
            "step_key": step_key,
            "step_id": str(step.id),
        })

    # ── preview_deploy: special handler (needs DB + run context) ──────────────
    if step_key == "preview_deploy":
        # Only deploy if all CI steps passed (caller ensures overall_ok before reaching here)
        ci_passed = True  # executor only calls preview_deploy if prior steps ok
        result_status, logs, duration_ms, ai_reasoning, preview_url = \
            await _run_preview_deploy(session, run, ci_passed)
    else:
        preview_url = None
        runner_fn = _CI_RUNNERS.get(step_key)
        if runner_fn is None:
            result_status = "skipped"
            logs = f"No runner registered for step '{step_key}'"
            duration_ms = 0
            ai_reasoning = "Skipped: unknown step key."
        else:
            try:
                result = await runner_fn(sandbox)
                result_status = result.status
                logs = result.logs
                duration_ms = result.duration_ms
                ai_reasoning = result.ai_reasoning
            except Exception as exc:
                logger.exception("Step runner %s raised unexpectedly", step_key)
                result_status = "failure"
                logs = f"Step runner crashed: {exc}"
                duration_ms = 0
                ai_reasoning = f"Unexpected error: {exc}"

    # Persist step result (first pass)
    step.status = PipelineStepStatus(result_status)
    step.logs = logs
    step.duration_ms = duration_ms
    step.ai_reasoning = ai_reasoning
    step.completed_at = _now()
    await session.commit()

    if emit_events:
        event_data: dict = {
            "run_id": str(run_id),
            "step_key": step_key,
            "step_id": str(step.id),
            "status": result_status,
            "duration_ms": duration_ms,
            "ai_reasoning": ai_reasoning,
        }
        if preview_url:
            event_data["preview_url"] = preview_url
        await event_bus.emit(str(run_id), "step_completed", event_data)

    return result_status, logs, duration_ms, ai_reasoning, preview_url


# ── Preview deploy step ───────────────────────────────────────────────────────

async def _run_preview_deploy(
    session: AsyncSession,
    run: PipelineRun,
    ci_passed: bool,
) -> tuple[str, str, int, str, str | None]:
    """Run the preview_deploy step.

    Returns (status, logs, duration_ms, ai_reasoning, preview_url|None).
    Skips if CI steps failed — no point deploying broken code.
    """
    if not ci_passed:
        return (
            "skipped",
            "Skipped: CI steps did not all pass.",
            0,
            "Deployment skipped because test/lint/build did not all pass.",
            None,
        )

    deployment = await session.scalar(
        select(Deployment).where(Deployment.run_id == run.id)
    )
    if deployment is None:
        return (
            "skipped",
            "No deployment record found for this run.",
            0,
            "Skipped: deployment row missing.",
            None,
        )

    from app.services import deployment_service
    updated = await deployment_service.deploy_preview(
        session,
        deployment=deployment,
        branch_name=run.branch_name,
        commit_sha=run.commit_sha,
    )
    await session.commit()

    status_map = {
        "healthy":   "success",
        "deploying": "running",
        "degraded":  "failure",
        "skipped":   "skipped",
    }
    step_status = status_map.get(str(updated.status), "skipped")

    logs = updated.deploy_logs or "No deployment logs."
    if updated.error_message:
        logs = f"Error: {updated.error_message}\n\n{logs}"

    dur = updated.duration_ms or 0
    if updated.preview_url:
        reasoning = f"Preview deployed at {updated.preview_url} in {dur}ms."
    elif step_status == "skipped":
        reasoning = updated.deploy_logs or "Deployment skipped."
    else:
        reasoning = f"Deployment failed: {updated.error_message or 'unknown error'}"

    # ── Phase 4: start post-deploy health monitoring ───────────────────────────
    if step_status == "success" and updated.preview_url:
        try:
            from app.models.deployment_config import DeploymentConfig
            from sqlalchemy import select as _select
            config = await session.scalar(
                _select(DeploymentConfig).where(
                    DeploymentConfig.project_id == updated.project_id,
                    DeploymentConfig.enabled.is_(True),
                )
            )
            health_path = (config.health_check_path if config else None) or "/health"
            monitor_mins = (config.monitor_duration_minutes if config else None) or 5

            from app.services.observability_service import start_monitoring, _record_start
            _record_start(updated.id)
            await start_monitoring(
                deployment_id=updated.id,
                project_id=updated.project_id,
                preview_url=updated.preview_url,
                health_check_path=health_path,
                monitor_duration_minutes=monitor_mins,
            )
        except Exception as exc:
            logger.warning("Failed to start health monitoring for dep %s: %s", updated.id, exc)

    return step_status, logs, dur, reasoning, updated.preview_url or None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_create_step(
    session: AsyncSession, run_id: UUID, step_key: str
) -> PipelineStep:
    """Return existing step row or create it (idempotent)."""
    existing = await session.scalar(
        select(PipelineStep).where(
            PipelineStep.run_id == run_id,
            PipelineStep.step_key == step_key,
        )
    )
    if existing is not None:
        return existing
    step = PipelineStep(run_id=run_id, step_key=step_key, status=PipelineStepStatus.PENDING)
    session.add(step)
    await session.flush()
    return step


def _build_summary(run: PipelineRun, success: bool) -> str:
    steps = run.steps or []
    step_parts = [
        f"{s.step_key}="
        + ("✓" if s.status == "success" else ("↷" if s.status == "skipped" else "✗"))
        + (f"[×{s.attempt}]" if s.attempt > 1 else "")
        for s in steps
    ]
    state = "passed" if success else "failed"
    return f"Pipeline {state}. Steps: {', '.join(step_parts) or 'none'}."
