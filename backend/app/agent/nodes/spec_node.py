"""SPEC generation node with timeout + audit hooks (US4/T032)."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context_builder import ContextBuilder
from app.config import settings
from app.models.agent_run import AgentRun
from app.models.stream_event import StreamEventType
from app.websocket.event_publisher import EventPublisher

try:
    from langgraph.types import interrupt
except Exception:  # pragma: no cover - fallback for local/unit environments
    def interrupt() -> None:  # type: ignore[override]
        return None


def _request_po_review_interrupt() -> None:
    """Pause for HIL after SPEC is written (initial generation or revision retry — T042)."""
    try:
        interrupt(None)
    except TypeError:
        interrupt()
    except RuntimeError:
        pass


StateDict = dict[str, Any]
AsyncCallable = Callable[..., Awaitable[Any]]


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


async def _publish_spec_status(state: StateDict, body: dict[str, Any]) -> None:
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


async def _audit(state: StateDict, action_type: str, description: str, *, final: bool = False) -> None:
    if final:
        await _call_async(state.get("finalise_log"), action_type=action_type, result=description)
        return
    await _call_async(
        state.get("write_pending_log"),
        action_type=action_type,
        action_description=description,
    )


async def _set_status(state: StateDict, new_status: str) -> None:
    await _call_async(state.get("set_agent_run_status"), new_status)
    state["agent_run_status"] = new_status


async def _publish_error(state: StateDict, message: str) -> None:
    await _call_async(state.get("publish_error"), message)


async def _persist_spec(state: StateDict, content: str) -> None:
    # Prefer injected persistence callback; fallback keeps content in state.
    persisted = await _call_async(state.get("persist_spec"), content)
    if persisted is None:
        state["spec_content"] = content
    else:
        state["spec_content"] = str(persisted)


async def _generate_spec(state: StateDict) -> StateDict:
    session = state.get("session")
    project_id = state.get("project_id")
    if session is None or project_id is None:
        raise ValueError("spec_node requires `session` and `project_id` in state.")

    context = await ContextBuilder.build_architect_context(project_id, session)
    intent = str(state.get("intent", "")).strip()
    feedback = str(state.get("feedback", "")).strip()
    if not intent and not feedback:
        raise ValueError("spec_node requires non-empty `intent` and/or `feedback`.")

    human_parts = [context["human"]]
    if intent:
        human_parts.append(f"Intent:\n{intent}")
    if feedback:
        human_parts.append(
            "The PO requested a revision of the current SPEC. Regenerate the full SPEC markdown, "
            "addressing the feedback while keeping coherent structure and headings."
        )
        human_parts.append(f"Revision feedback:\n{feedback}")
    human_content = "\n\n".join(human_parts)

    await _publish_spec_status(
        state,
        {
            "from": "IDLE",
            "to": "SPEC_GENERATION",
            "reason": (
                "Regenerating SPEC from PO revision feedback."
                if feedback
                else "Generating SPEC from intent and constitution."
            ),
        },
    )
    state["spec_generation_stream"] = True

    if feedback:
        await _audit(state, "llm_call", "Regenerate SPEC from PO revision feedback + constitution")
    else:
        await _audit(state, "llm_call", "Generate SPEC from intent + constitution")
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
    spec_markdown = str(llm_response.content).strip()
    if not spec_markdown:
        raise ValueError("LLM returned empty SPEC content.")

    await _audit(state, "write_file", "Persist generated SPEC")
    await _persist_spec(state, spec_markdown)

    await _publish_spec_status(
        state,
        {
            "from": "SPEC_GENERATION",
            "to": "AWAITING_HIL",
            "reason": "SPEC draft ready for PO review.",
        },
    )

    await _set_status(state, "awaiting_hil")
    await _audit(state, "spec_node", "success", final=True)
    _request_po_review_interrupt()
    return state


async def run(state: StateDict) -> StateDict:
    """LangGraph node entrypoint for SPEC generation."""
    try:
        return await asyncio.wait_for(_generate_spec(state), timeout=60.0)
    except asyncio.TimeoutError:
        message = "Spec generation exceeded 60-second limit. Please retry."
        state["error"] = message
        frm = "SPEC_GENERATION" if state.get("spec_generation_stream") else "IDLE"
        await _publish_spec_status(
            state,
            {"from": frm, "to": "TIMEOUT", "reason": message},
        )
        await _set_status(state, "timeout")
        await _publish_error(state, message)
        await _audit(state, "spec_node", "timeout", final=True)
        return state
    except Exception as exc:
        state["error"] = str(exc)
        frm = "SPEC_GENERATION" if state.get("spec_generation_stream") else "IDLE"
        await _publish_spec_status(
            state,
            {"from": frm, "to": "FAILED", "reason": str(exc)},
        )
        await _set_status(state, "failure")
        await _publish_error(state, str(exc))
        await _audit(state, "spec_node", "failure", final=True)
        return state
