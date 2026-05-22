"""Background reviewer agent after coder produces a diff (Phase C)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from app.agent.nodes import reviewer_node
from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.services.review_orchestration_service import ReviewOrchestrationService

logger = logging.getLogger(__name__)


def schedule_reviewer_for_task(
    project_id: UUID,
    task_id: UUID,
    *,
    diff_id: UUID,
) -> None:
    from app.config import settings

    if not settings.agent_reviewer_enabled:
        return
    asyncio.create_task(_run_reviewer_background(project_id, task_id, diff_id))


async def _run_reviewer_background(project_id: UUID, task_id: UUID, diff_id: UUID) -> None:
    async with async_session_maker() as session:
        agent_run = AgentRun(
            project_id=project_id,
            task_id=task_id,
            agent_type=AgentType.REVIEWER,
            agent_version="1.0.0",
            status=AgentRunStatus.RUNNING,
            input_artifacts=[str(diff_id)],
            output_artifacts=[],
        )
        session.add(agent_run)
        await session.flush()
        agent_run_id = agent_run.id
        await session.commit()

    async with async_session_maker() as session:
        try:
            state = {
                "session": session,
                "project_id": project_id,
                "task_id": task_id,
                "diff_id": diff_id,
                "agent_run_id": agent_run_id,
            }
            out = await reviewer_node.run(state)
            result = out.get("review_result") if isinstance(out.get("review_result"), dict) else None
            if not result:
                run = await session.get(AgentRun, agent_run_id)
                if run is not None and isinstance(run.result, dict):
                    result = run.result
            await session.commit()
            if result:
                await ReviewOrchestrationService.apply_reviewer_result(
                    project_id,
                    task_id,
                    diff_id=diff_id,
                    result=result,
                )
        except Exception as exc:
            logger.exception("Reviewer failed task_id=%s", task_id)
            await session.rollback()
            async with async_session_maker() as session2:
                run = await session2.get(AgentRun, agent_run_id)
                if run is not None:
                    run.status = AgentRunStatus.FAILURE
                    run.completed_at = datetime.now(timezone.utc)
                    run.result = {"error": f"Reviewer agent failed: {exc}"}
                    await session2.commit()
            await ReviewOrchestrationService.apply_reviewer_result(
                project_id,
                task_id,
                diff_id=diff_id,
                result={
                    "verdict": "unclear",
                    "summary": f"Reviewer agent failed ({exc}). Please review the diff manually.",
                    "findings": [],
                },
            )
