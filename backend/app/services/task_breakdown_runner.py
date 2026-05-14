"""Background PLAN → Kanban task breakdown (US7 / T048)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import task_breakdown_node
from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus

logger = logging.getLogger(__name__)


async def _noop(*_a: object, **_kw: object) -> None:
    return None


async def run_task_breakdown_task(project_id: UUID, agent_run_id: UUID) -> None:
    """Run ``task_breakdown_node`` after PLAN approval (REST-triggered; graph may also resume here)."""
    async with async_session_maker() as session:
        try:
            await _run_with_session(session, project_id=project_id, agent_run_id=agent_run_id)
            await session.commit()
        except Exception:
            logger.exception("Task breakdown failed for agent_run_id=%s", agent_run_id)
            await session.rollback()
            async with async_session_maker() as session2:
                run = await session2.get(AgentRun, agent_run_id)
                if run is not None:
                    run.status = AgentRunStatus.FAILURE
                    run.completed_at = datetime.now(timezone.utc)
                    await session2.commit()


async def _run_with_session(
    session: AsyncSession,
    *,
    project_id: UUID,
    agent_run_id: UUID,
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
        "set_agent_run_status": set_agent_run_status,
        "publish_error": _noop,
    }
    await task_breakdown_node.run(state)
