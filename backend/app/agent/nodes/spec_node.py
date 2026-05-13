"""SPEC generation node with timeout + audit hooks (US4/T032)."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.agent.context_builder import ContextBuilder
from app.config import settings

try:
    from langgraph.types import interrupt
except Exception:  # pragma: no cover - fallback for local/unit environments
    def interrupt() -> None:  # type: ignore[override]
        return None


StateDict = dict[str, Any]
AsyncCallable = Callable[..., Awaitable[Any]]


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
        human_parts.append(f"Revision feedback:\n{feedback}")
    human_content = "\n\n".join(human_parts)

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

    await _set_status(state, "awaiting_hil")
    await _audit(state, "spec_node", "success", final=True)
    try:
        interrupt(None)
    except TypeError:
        interrupt()
    except RuntimeError:
        pass
    return state


async def run(state: StateDict) -> StateDict:
    """LangGraph node entrypoint for SPEC generation."""
    try:
        return await asyncio.wait_for(_generate_spec(state), timeout=60.0)
    except asyncio.TimeoutError:
        message = "Spec generation exceeded 60-second limit. Please retry."
        state["error"] = message
        await _set_status(state, "timeout")
        await _publish_error(state, message)
        await _audit(state, "spec_node", "timeout", final=True)
        return state
    except Exception as exc:
        state["error"] = str(exc)
        await _set_status(state, "failure")
        await _publish_error(state, str(exc))
        await _audit(state, "spec_node", "failure", final=True)
        return state
