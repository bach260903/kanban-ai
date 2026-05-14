"""PLAN generation from approved SPEC + constitution (US6 / T044)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context_builder import ContextBuilder
from app.config import settings
from app.exceptions import NotFoundError
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.audit_log import AuditLogResult
from app.models.document import DocumentStatus, DocumentType
from app.models.stream_event import StreamEventType
from app.services.audit_service import finalise_log, write_audit, write_pending_log
from app.services.document_service import DocumentService
from app.websocket.event_publisher import EventPublisher

try:
    from langgraph.types import interrupt
except Exception:  # pragma: no cover - fallback for local/unit environments
    def interrupt() -> None:  # type: ignore[override]
        return None


def _request_po_review_interrupt() -> None:
    try:
        interrupt(None)
    except TypeError:
        interrupt()
    except RuntimeError:
        pass


StateDict = dict[str, Any]


async def _resolve_stream_task_id(state: StateDict, session: AsyncSession) -> UUID | None:
    tid = state.get("task_id")
    if isinstance(tid, UUID):
        return tid
    aid = state.get("agent_run_id")
    if isinstance(aid, UUID):
        run = await session.get(AgentRun, aid)
        if run is not None and run.task_id is not None:
            return run.task_id
    return None


async def _publish_plan_status(state: StateDict, body: dict[str, Any]) -> None:
    """Thought-stream STATUS_CHANGE when a task scope exists (``stream_events.task_id`` FK)."""
    raw = state.get("session")
    if not isinstance(raw, AsyncSession):
        return
    task_id = await _resolve_stream_task_id(state, raw)
    if task_id is None:
        return
    aid = state.get("agent_run_id")
    ar = aid if isinstance(aid, UUID) else None
    await EventPublisher.publish(
        task_id,
        StreamEventType.STATUS_CHANGE,
        json.dumps(body, separators=(",", ":")),
        raw,
        ar,
    )


async def _call_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    if callable(fn):
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    return None


async def _set_status(state: StateDict, new_status: str) -> None:
    await _call_async(state.get("set_agent_run_status"), new_status)
    state["agent_run_status"] = new_status


async def _publish_error(state: StateDict, message: str) -> None:
    await _call_async(state.get("publish_error"), message)


async def _set_agent_run_inline(session: AsyncSession, agent_run_id: UUID, new_status: str) -> None:
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


async def _apply_agent_run_status(state: StateDict, new_status: str) -> None:
    if state.get("set_agent_run_status"):
        await _set_status(state, new_status)
        return
    session = state.get("session")
    agent_run_id = state.get("agent_run_id")
    if session is not None and agent_run_id is not None:
        await _set_agent_run_inline(session, agent_run_id, new_status)


async def _generate_plan(state: StateDict) -> StateDict:
    session = state.get("session")
    project_id = state.get("project_id")
    agent_run_id = state.get("agent_run_id")
    if session is None or project_id is None or agent_run_id is None:
        raise ValueError("plan_node requires `session`, `project_id`, and `agent_run_id` in state.")
    if not isinstance(project_id, UUID) or not isinstance(agent_run_id, UUID):
        raise ValueError("plan_node `project_id` and `agent_run_id` must be UUID instances.")

    task_id: UUID | None = state.get("task_id")
    if task_id is not None and not isinstance(task_id, UUID):
        raise ValueError("plan_node `task_id` must be a UUID or None.")

    feedback = str(state.get("feedback", "")).strip()

    spec_doc = await DocumentService.get_by_type(session, project_id, DocumentType.SPEC)
    if spec_doc.status != DocumentStatus.APPROVED:
        raise ValueError("SPEC must be approved before generating PLAN.")

    spec_markdown = spec_doc.content.strip()
    if not spec_markdown:
        raise ValueError("Approved SPEC has no content.")

    try:
        plan_doc = await DocumentService.get_by_type(session, project_id, DocumentType.PLAN)
    except NotFoundError:
        plan_doc = await DocumentService.create(session, project_id, DocumentType.PLAN, "")

    context = await ContextBuilder.build_plan_context(project_id, session, spec_markdown)
    human_parts = [context["human"]]
    if feedback:
        human_parts.append(
            "The PO requested a revision of the current PLAN. Regenerate the full PLAN.md markdown, "
            "addressing the feedback while staying aligned with the approved SPEC."
        )
        human_parts.append(f"Revision feedback:\n{feedback}")
    human_content = "\n\n".join(human_parts)

    await _publish_plan_status(
        state,
        {
            "from": "IDLE",
            "to": "PLAN_GENERATION",
            "reason": (
                "Regenerating PLAN from PO revision feedback."
                if feedback
                else "Generating PLAN from approved SPEC and constitution."
            ),
        },
    )
    state["plan_generation_stream"] = True

    if feedback:
        llm_desc = "Regenerate PLAN from PO revision feedback + approved SPEC + constitution"
    else:
        llm_desc = "Generate PLAN from approved SPEC + constitution"

    llm_log = await write_pending_log(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="llm_call",
        action_description=llm_desc,
        input_refs=[str(spec_doc.id), str(plan_doc.id)],
    )
    try:
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=0.2,
        )
        llm_response = await llm.ainvoke(
            [
                SystemMessage(content=context["system"]),
                HumanMessage(content=human_content),
            ]
        )
        plan_markdown = str(llm_response.content).strip()
        if not plan_markdown:
            raise ValueError("LLM returned empty PLAN content.")
    except Exception:
        await finalise_log(session, llm_log.id, AuditLogResult.FAILURE)
        raise
    else:
        await finalise_log(session, llm_log.id, AuditLogResult.SUCCESS)

    write_log = await write_pending_log(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="write_file",
        action_description="Persist generated PLAN to documents table",
        input_refs=[str(plan_doc.id)],
    )
    try:
        plan_doc.content = plan_markdown
        plan_doc.updated_at = datetime.now(timezone.utc)
        if feedback:
            plan_doc.version = int(plan_doc.version) + 1
        await session.flush()
    except Exception:
        await finalise_log(session, write_log.id, AuditLogResult.FAILURE)
        raise
    else:
        await finalise_log(
            session,
            write_log.id,
            AuditLogResult.SUCCESS,
            output_refs=[str(plan_doc.id)],
        )

    await _apply_agent_run_status(state, AgentRunStatus.AWAITING_HIL.value)

    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="plan_node",
        action_description="PLAN generation succeeded; awaiting PO review",
        result=AuditLogResult.SUCCESS,
        input_refs=[str(plan_doc.id)],
        output_refs=[str(plan_doc.id)],
    )
    await _publish_plan_status(
        state,
        {
            "from": "PLAN_GENERATION",
            "to": "AWAITING_HIL",
            "reason": "PLAN draft ready for PO review.",
        },
    )
    _request_po_review_interrupt()

    return state


async def run(state: StateDict) -> StateDict:
    """LangGraph node entrypoint for PLAN generation."""
    try:
        return await asyncio.wait_for(_generate_plan(state), timeout=60.0)
    except asyncio.TimeoutError:
        message = "Plan generation exceeded 60-second limit. Please retry."
        state["error"] = message
        frm = "PLAN_GENERATION" if state.get("plan_generation_stream") else "IDLE"
        await _publish_plan_status(
            state,
            {"from": frm, "to": "TIMEOUT", "reason": message},
        )
        await _apply_agent_run_status(state, AgentRunStatus.TIMEOUT.value)
        await _publish_error(state, message)
        session = state.get("session")
        project_id = state.get("project_id")
        task_id: UUID | None = state.get("task_id")
        if session is not None and isinstance(project_id, UUID):
            try:
                await write_audit(
                    session,
                    project_id=project_id,
                    task_id=task_id,
                    action_type="plan_node",
                    action_description=message,
                    result=AuditLogResult.FAILURE,
                )
            except Exception:
                pass
        return state
    except Exception as exc:
        state["error"] = str(exc)
        frm = "PLAN_GENERATION" if state.get("plan_generation_stream") else "IDLE"
        await _publish_plan_status(
            state,
            {"from": frm, "to": "FAILED", "reason": str(exc)},
        )
        await _apply_agent_run_status(state, AgentRunStatus.FAILURE.value)
        await _publish_error(state, str(exc))
        session = state.get("session")
        project_id = state.get("project_id")
        task_id = state.get("task_id")
        if session is not None and isinstance(project_id, UUID):
            try:
                await write_audit(
                    session,
                    project_id=project_id,
                    task_id=task_id if isinstance(task_id, UUID) else None,
                    action_type="plan_node",
                    action_description=str(exc),
                    result=AuditLogResult.FAILURE,
                )
            except Exception:
                pass
        return state
