"""Pause / resume coordination for coder agent (US11 / T084)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_pause_state import AgentPauseState, PauseRunState
from app.models.agent_run import AgentRun, AgentType
from app.websocket.event_publisher import _get_redis

logger = logging.getLogger(__name__)


async def _latest_coder_run_id(session: AsyncSession, task_id: UUID) -> UUID | None:
    result = await session.execute(
        select(AgentRun.id)
        .where(AgentRun.task_id == task_id, AgentRun.agent_type == AgentType.CODER)
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


class PauseService:
    """Redis pause flag + ``agent_pause_states`` row (aligned with WebSocket PAUSE/RESUME)."""

    @staticmethod
    async def pause(session: AsyncSession, task_id: UUID) -> None:
        """SET ``pause:{task_id}`` in Redis; persist ``paused`` in ``agent_pause_states`` when a coder run exists."""
        r = await _get_redis()
        await r.set(f"pause:{task_id}", "1")
        run_id = await _latest_coder_run_id(session, task_id)
        if run_id is None:
            await session.flush()
            return
        now = datetime.now(timezone.utc)
        row = await session.scalar(select(AgentPauseState).where(AgentPauseState.task_id == task_id))
        if row is None:
            session.add(
                AgentPauseState(
                    task_id=task_id,
                    agent_run_id=run_id,
                    state=PauseRunState.PAUSED,
                    paused_at=now,
                )
            )
        else:
            row.state = PauseRunState.PAUSED
            row.paused_at = now
        await session.flush()

    @staticmethod
    async def resume(session: AsyncSession, task_id: UUID, instructions: str | None = None) -> None:
        """DEL ``pause:{task_id}``; set ``running`` and steering instructions on ``agent_pause_states``."""
        r = await _get_redis()
        await r.delete(f"pause:{task_id}")
        run_id = await _latest_coder_run_id(session, task_id)
        if run_id is None:
            await session.flush()
            return
        now = datetime.now(timezone.utc)
        row = await session.scalar(select(AgentPauseState).where(AgentPauseState.task_id == task_id))
        if row is None:
            session.add(
                AgentPauseState(
                    task_id=task_id,
                    agent_run_id=run_id,
                    state=PauseRunState.RUNNING,
                    steering_instructions=instructions,
                    resumed_at=now,
                )
            )
        else:
            row.state = PauseRunState.RUNNING
            row.steering_instructions = instructions
            row.resumed_at = now
        await session.flush()

    @staticmethod
    async def is_paused(task_id: UUID) -> bool:
        """True if Redis ``pause:{task_id}`` is set."""
        try:
            r = await _get_redis()
            n = await r.exists(f"pause:{task_id}")
            return bool(n)
        except Exception:
            logger.exception("is_paused Redis check failed task_id=%s", task_id)
            raise
