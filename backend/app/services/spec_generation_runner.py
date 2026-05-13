"""Background SPEC generation (US4 / T037)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import spec_node
from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.document import Document

logger = logging.getLogger(__name__)


async def _noop(*_a: object, **_kw: object) -> None:
    return None


async def run_generate_spec_task(
    project_id: UUID,
    agent_run_id: UUID,
    document_id: UUID,
    intent_text: str,
    *,
    feedback: str | None = None,
) -> None:
    """Run ``spec_node`` in a fresh DB session (``generate-spec`` or revision)."""
    async with async_session_maker() as session:
        try:
            await _run_with_session(
                session,
                project_id=project_id,
                agent_run_id=agent_run_id,
                document_id=document_id,
                intent_text=intent_text,
                feedback=feedback,
            )
            await session.commit()
        except Exception:
            logger.exception("SPEC generation failed for agent_run_id=%s", agent_run_id)
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
    document_id: UUID,
    intent_text: str,
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

    feedback_text = (feedback or "").strip()

    async def persist_spec(content: str) -> str:
        doc = await session.get(Document, document_id)
        if doc is None:
            raise ValueError("SPEC document missing.")
        doc.content = content
        doc.updated_at = datetime.now(timezone.utc)
        if feedback_text:
            doc.version = int(doc.version) + 1
        await session.flush()
        return content

    state: dict[str, Any] = {
        "session": session,
        "project_id": project_id,
        "agent_run_id": agent_run_id,
        "intent": intent_text,
        "feedback": feedback or "",
        "set_agent_run_status": set_agent_run_status,
        "persist_spec": persist_spec,
        "write_pending_log": _noop,
        "finalise_log": _noop,
        "publish_error": _noop,
    }
    await spec_node.run(state)
