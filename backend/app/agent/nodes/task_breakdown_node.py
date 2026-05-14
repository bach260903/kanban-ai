"""Decompose an approved PLAN into Kanban ``Task`` rows (US7 / T047)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.document import DocumentStatus, DocumentType
from app.services.document_service import DocumentService
from app.services.task_service import TaskBulkItem, TaskService

logger = logging.getLogger(__name__)

StateDict = dict[str, Any]
_MAX_TASKS = 80


class TaskBreakdownItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    priority: int = 0


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _parse_task_payload(raw: str) -> list[TaskBreakdownItem]:
    blob = _strip_json_fence(raw)
    data = json.loads(blob)
    if isinstance(data, list):
        items_raw: list[Any] = data
    elif isinstance(data, dict) and "tasks" in data:
        inner = data["tasks"]
        if not isinstance(inner, list):
            raise ValueError("`tasks` must be a JSON array.")
        items_raw = inner
    else:
        raise ValueError("LLM output must be a JSON array or an object with a `tasks` array.")

    ta = TypeAdapter(list[TaskBreakdownItem])
    return ta.validate_python(items_raw)


async def _call_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    if callable(fn):
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    return None


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
        await _call_async(state["set_agent_run_status"], new_status)
        return
    session = state.get("session")
    agent_run_id = state.get("agent_run_id")
    if session is not None and isinstance(agent_run_id, UUID):
        await _set_agent_run_inline(session, agent_run_id, new_status)


async def _publish_error(state: StateDict, message: str) -> None:
    await _call_async(state.get("publish_error"), message)


async def _run_task_breakdown(state: StateDict) -> StateDict:
    session = state.get("session")
    project_id = state.get("project_id")
    agent_run_id = state.get("agent_run_id")
    if session is None or project_id is None or agent_run_id is None:
        raise ValueError("task_breakdown_node requires `session`, `project_id`, and `agent_run_id`.")
    if not isinstance(project_id, UUID) or not isinstance(agent_run_id, UUID):
        raise ValueError("`project_id` and `agent_run_id` must be UUID instances.")

    plan_doc = await DocumentService.get_by_type(session, project_id, DocumentType.PLAN)
    if plan_doc.status != DocumentStatus.APPROVED:
        raise ValueError("PLAN must be approved before task breakdown.")
    plan_markdown = plan_doc.content.strip()
    if not plan_markdown:
        raise ValueError("Approved PLAN has no content.")

    system = (
        "You are a project planning assistant. Read the PLAN.md markdown and extract concrete "
        "engineering or product tasks suitable for a Kanban board.\n"
        "Reply with **only** valid JSON: either a top-level array, or an object "
        '`{"tasks": [...]}` where each element has:\n'
        '- "title" (string, required, max 500 chars)\n'
        '- "description" (string, optional)\n'
        '- "priority" (integer; lower means higher urgency; default 0)\n'
        "Produce between 3 and 40 tasks when the PLAN is substantial; fewer if the PLAN is tiny. "
        "Do not include tasks that are only meta-documentation."
    )
    human = f"## Approved PLAN\n\n{plan_markdown}\n"

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.1,
    )
    llm_response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
    raw = str(llm_response.content).strip()
    if not raw:
        raise ValueError("LLM returned empty response.")

    items = _parse_task_payload(raw)
    if not items:
        raise ValueError("LLM returned zero tasks.")
    if len(items) > _MAX_TASKS:
        items = items[:_MAX_TASKS]
        logger.warning("Task breakdown truncated to %s tasks", _MAX_TASKS)

    bulk_inputs: list[TaskBulkItem] = []
    for it in items:
        title = it.title.strip()[:500]
        if not title:
            continue
        desc = (it.description or "").strip() or None
        bulk_inputs.append(TaskBulkItem(title=title, description=desc, priority=int(it.priority)))
    if not bulk_inputs:
        raise ValueError("No valid tasks after parsing LLM output.")
    created = await TaskService.create_bulk(session, project_id, bulk_inputs)

    state["tasks_created"] = len(created)
    await _apply_agent_run_status(state, AgentRunStatus.SUCCESS.value)
    return state


async def run(state: StateDict) -> StateDict:
    """LangGraph node: PLAN → structured tasks (no HIL interrupt)."""
    try:
        return await asyncio.wait_for(_run_task_breakdown(state), timeout=90.0)
    except asyncio.TimeoutError:
        msg = "Task breakdown exceeded time limit. Please retry."
        state["error"] = msg
        await _apply_agent_run_status(state, AgentRunStatus.TIMEOUT.value)
        await _publish_error(state, msg)
        return state
    except Exception as exc:
        logger.exception("task_breakdown_node failed")
        state["error"] = str(exc)
        await _apply_agent_run_status(state, AgentRunStatus.FAILURE.value)
        await _publish_error(state, str(exc))
        return state
