"""Read latest reviewer agent output for a task."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentType
from app.schemas.review_insight import ReviewInsightResponse


class ReviewInsightService:
    @staticmethod
    async def get_for_task(session: AsyncSession, task_id: UUID) -> ReviewInsightResponse:
        result = await session.execute(
            select(AgentRun)
            .where(AgentRun.task_id == task_id, AgentRun.agent_type == AgentType.REVIEWER)
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if run is None:
            return ReviewInsightResponse(available=False)
        raw = run.result if isinstance(run.result, dict) else None
        insight = ReviewInsightResponse.from_agent_result(run.id, run.status, raw)
        insight.updated_at = run.completed_at or run.started_at
        return insight
