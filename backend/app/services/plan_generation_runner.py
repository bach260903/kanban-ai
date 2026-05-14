"""Background PLAN generation (US6 / T045)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import plan_node
from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus

logger = logging.getLogger(__name__)


async def _noop(*_a: object, **_kw: object) -> None:
    return None


async def run_generate_plan_task(
    project_id: UUID,
    agent_run_id: UUID,
    *,
    feedback: str | None = None,
) -> None:
    """Run ``plan_node`` in a fresh DB session (``generate-plan`` or future PLAN revision)."""
    async with async_session_maker() as session:
        try:
            await _run_plan_with_session(
                session,
                project_id=project_id,
                agent_run_id=agent_run_id,
                feedback=feedback,
            )
            await session.commit()
        except Exception:
            logger.exception("PLAN generation failed for agent_run_id=%s", agent_run_id)
            await session.rollback()
            async with async_session_maker() as session2:
                run = await session2.get(AgentRun, agent_run_id)
                if run is not None:
                    run.status = AgentRunStatus.FAILURE
                    run.completed_at = datetime.now(timezone.utc)
                    await session2.commit()


async def _run_plan_with_session(
    session: AsyncSession,
    *,
    project_id: UUID,
    agent_run_id: UUID,
    feedback: str | None = None,
) -> None:
    async def set_agent_run_status(new_status: str) -> None:
        run = await session.get(AgentRun, agent_run_id)
        if run is None:
            return
        run.status = AgentRunStatus(new_status)
        if new_status in (
            AgentRunStatus.FAILURE.value,
            AgentRunStatus.TIMEOUT.value,
            AgentRunStatus.SUCCESS.value,
        ):
            run.completed_at = datetime.now(timezone.utc)
        await session.flush()

    state: dict[str, Any] = {
        "session": session,
        "project_id": project_id,
        "agent_run_id": agent_run_id,
        "task_id": None,
        "feedback": feedback or "",
        "set_agent_run_status": set_agent_run_status,
        "publish_error": _noop,
    }
    await plan_node.run(state)
