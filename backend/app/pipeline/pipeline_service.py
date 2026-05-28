"""Pipeline service — CRUD and trigger logic."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_step import PipelineStep, PipelineStepStatus
from app.models.deployment import Deployment, DeploymentStatus
from app.pipeline.executor import STEP_ORDER, execute_pipeline

logger = logging.getLogger(__name__)


class PipelineService:

    @staticmethod
    async def create_and_trigger(
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID | None,
        sandbox: Path,
        triggered_by: str = "task_approved",
        branch_name: str | None = None,
        commit_sha: str | None = None,
    ) -> PipelineRun:
        """Create a PipelineRun with pending steps and fire the executor in the background.

        The HTTP request is NOT blocked — execution happens in an asyncio background task.
        """
        run = PipelineRun(
            project_id=project_id,
            task_id=task_id,
            status=PipelineRunStatus.QUEUED,
            triggered_by=triggered_by,
            branch_name=branch_name,
            commit_sha=commit_sha,
        )
        session.add(run)
        await session.flush()  # get run.id

        # Pre-create step rows as PENDING so UI can render the full pipeline immediately
        for step_key in STEP_ORDER:
            session.add(PipelineStep(
                run_id=run.id,
                step_key=step_key,
                status=PipelineStepStatus.PENDING,
            ))

        # Create deployment record — status starts PENDING; executor updates it
        deployment = Deployment(
            project_id=project_id,
            task_id=task_id,
            run_id=run.id,
            status=DeploymentStatus.PENDING,
            branch_name=branch_name,
            commit_sha=commit_sha,
        )
        session.add(deployment)
        await session.flush()

        # Commit before launching background task so rows exist in DB
        await session.commit()

        # Fire background — do NOT await
        run_id = run.id
        asyncio.create_task(
            _safe_execute(run_id, sandbox),
            name=f"pipeline-{run_id}",
        )

        logger.info(
            "Pipeline run %s created for task=%s project=%s",
            run_id, task_id, project_id,
        )
        return run

    @staticmethod
    async def get_run(session: AsyncSession, run_id: UUID) -> PipelineRun | None:
        return await session.get(PipelineRun, run_id)

    @staticmethod
    async def list_runs_for_project(
        session: AsyncSession,
        project_id: UUID,
        limit: int = 20,
    ) -> list[PipelineRun]:
        result = await session.execute(
            select(PipelineRun)
            .where(PipelineRun.project_id == project_id)
            .order_by(PipelineRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_runs_for_task(
        session: AsyncSession,
        task_id: UUID,
    ) -> list[PipelineRun]:
        result = await session.execute(
            select(PipelineRun)
            .where(PipelineRun.task_id == task_id)
            .order_by(PipelineRun.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_deployments_for_project(
        session: AsyncSession,
        project_id: UUID,
        limit: int = 30,
    ) -> list[Deployment]:
        result = await session.execute(
            select(Deployment)
            .where(Deployment.project_id == project_id)
            .order_by(Deployment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def _safe_execute(run_id: UUID, sandbox: Path) -> None:
    """Wrapper that catches all exceptions so a crashing pipeline doesn't kill the event loop."""
    try:
        await execute_pipeline(run_id, sandbox)
    except Exception:
        logger.exception("Unhandled exception in pipeline executor run_id=%s", run_id)
