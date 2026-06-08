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
from app.models.audit_log import AuditLogResult
from app.models.document import Document
import app.services.audit_service as audit_service
from app.services.audit_service import ARCHITECT_AGENT_ID

logger = logging.getLogger(__name__)


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

    _pending_log_id: list[Any] = [None]

    async def write_pending_log_cb(*, action_type: str, action_description: str) -> None:
        log = await audit_service.write_pending_log(
            session,
            project_id=project_id,
            task_id=None,
            action_type=action_type,
            action_description=action_description,
            agent_id=ARCHITECT_AGENT_ID,
        )
        _pending_log_id[0] = log.id

    async def finalise_log_cb(*, action_type: str, result: str) -> None:
        log_id = _pending_log_id[0]
        if log_id is not None:
            await audit_service.finalise_log(session, log_id, result)
            _pending_log_id[0] = None
        else:
            coerced = AuditLogResult.SUCCESS if "success" in result.lower() else AuditLogResult.FAILURE
            await audit_service.write_audit(
                session,
                project_id=project_id,
                task_id=None,
                action_type=action_type,
                action_description=result,
                result=coerced,
                agent_id=ARCHITECT_AGENT_ID,
            )

    async def _noop(*_a: object, **_kw: object) -> None:
        return None

    # Fetch current SPEC content so the revision prompt can show it to the LLM.
    # Without this the model has to regenerate from scratch instead of making
    # targeted edits — losing good sections already approved by the PO.
    current_doc = await session.get(Document, document_id)
    current_spec_content = (current_doc.content or "").strip() if current_doc else ""

    state: dict[str, Any] = {
        "session": session,
        "project_id": project_id,
        "agent_run_id": agent_run_id,
        "intent": intent_text,
        "feedback": feedback or "",
        "current_spec_content": current_spec_content,
        "set_agent_run_status": set_agent_run_status,
        "persist_spec": persist_spec,
        "write_pending_log": write_pending_log_cb,
        "finalise_log": finalise_log_cb,
        "publish_error": _noop,
    }
    await spec_node.run(state)
