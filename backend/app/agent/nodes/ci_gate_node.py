"""CI gate node — trigger pipeline and wait for result before HIL (T-ci-gate).

Flow:
  Coder finishes → ci_gate → CI pass  → reviewer → HIL (human)
                           → CI fail, retry < 2 → coder (with failure context)
                           → CI fail, max retries → reviewer → HIL (human sees report)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_step import PipelineStep
from app.pipeline.pipeline_service import PipelineService

logger = logging.getLogger(__name__)

StateDict = dict[str, Any]

_CI_POLL_INTERVAL = 5       # seconds between status polls
_CI_TIMEOUT = 300           # 5 minutes max wait
_MAX_CI_RETRIES = 2         # how many times to send coder back for CI failures


def _sandbox_path(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    return (root / str(project_id)).resolve()


def _build_failure_report(steps: list[PipelineStep]) -> str:
    """Summarise failed steps into a concise report for coder / human."""
    lines: list[str] = ["CI pipeline failed. Failed steps:"]
    for step in steps:
        if step.status.value in ("failure", "error"):
            lines.append(f"\n### {step.step_key}")
            if step.logs:
                # Keep last 60 lines to stay within token budget
                tail = "\n".join(step.logs.splitlines()[-60:])
                lines.append(f"```\n{tail}\n```")
    return "\n".join(lines) if len(lines) > 1 else "CI failed — no step output available."


async def _wait_for_pipeline(session: AsyncSession, run_id: UUID) -> PipelineRun:
    """Poll the pipeline run until it reaches a terminal status or times out."""
    elapsed = 0
    while elapsed < _CI_TIMEOUT:
        await asyncio.sleep(_CI_POLL_INTERVAL)
        elapsed += _CI_POLL_INTERVAL
        # Expire cache so we get fresh data from DB
        session.expire_all()
        run = await session.get(PipelineRun, run_id)
        if run is None:
            raise RuntimeError(f"PipelineRun {run_id} disappeared from DB.")
        if run.status not in (PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING):
            return run
    raise asyncio.TimeoutError(f"CI pipeline {run_id} did not finish within {_CI_TIMEOUT}s.")


async def run(state: StateDict) -> StateDict:
    """LangGraph node: trigger CI pipeline and block until result is known."""
    session: AsyncSession | None = state.get("session")
    project_id: UUID | None = state.get("project_id")
    task_id: UUID | None = state.get("task_id")

    if session is None or project_id is None:
        logger.warning("ci_gate_node: missing session or project_id — skipping CI.")
        state["ci_passed"] = True
        return state

    retry_count: int = state.get("ci_retry_count") or 0

    try:
        sandbox = _sandbox_path(project_id)
        pipeline_run = await PipelineService.create_and_trigger(
            session,
            project_id=project_id,
            task_id=task_id,
            sandbox=sandbox,
            triggered_by="agent_ci_gate",
        )
        state["ci_run_id"] = pipeline_run.id

        logger.info(
            "ci_gate_node: pipeline %s triggered for project=%s task=%s (retry=%d)",
            pipeline_run.id, project_id, task_id, retry_count,
        )

        finished_run = await _wait_for_pipeline(session, pipeline_run.id)

        if finished_run.status == PipelineRunStatus.SUCCESS:
            logger.info("ci_gate_node: CI passed (run=%s)", finished_run.id)
            state["ci_passed"] = True
            state["ci_failure_report"] = ""
        else:
            # Fetch steps with output for failure report
            fresh = await session.get(PipelineRun, finished_run.id)
            steps = fresh.steps if fresh else []
            report = _build_failure_report(steps)
            state["ci_passed"] = False
            state["ci_failure_report"] = report
            state["ci_retry_count"] = retry_count + 1
            logger.warning(
                "ci_gate_node: CI failed (run=%s retry=%d/%d)",
                finished_run.id, retry_count + 1, _MAX_CI_RETRIES,
            )

    except asyncio.TimeoutError:
        logger.error("ci_gate_node: timeout waiting for pipeline project=%s", project_id)
        state["ci_passed"] = False
        state["ci_failure_report"] = "CI pipeline timed out after 5 minutes."
        state["ci_retry_count"] = retry_count + 1

    except Exception as exc:
        logger.exception("ci_gate_node: unexpected error project=%s", project_id)
        state["ci_passed"] = False
        state["ci_failure_report"] = f"CI gate error: {exc}"
        state["ci_retry_count"] = retry_count + 1

    return state


def route(state: StateDict) -> str:
    """Routing function called by graph after ci_gate_node."""
    if state.get("ci_passed"):
        return "reviewer_node"
    retry_count = state.get("ci_retry_count") or 0
    if retry_count < _MAX_CI_RETRIES:
        # Send back to coder with failure context injected into state
        backend = str(state.get("coding_backend", "groq"))
        return "cli_coder_node" if backend in ("claude_code", "gemini") else "coder_node"
    # Max retries exhausted — escalate to reviewer → HIL with failure report
    return "reviewer_node"
