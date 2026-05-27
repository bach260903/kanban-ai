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
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.llm.factory import create_architect_llm, require_llm_configured
from app.llm.invoke_helpers import ainvoke_llm
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
    acceptance_criteria: list[str] = Field(default_factory=list)
    plan_reference: str = ""
    files_hint: list[str] = Field(default_factory=list)
    priority: int = 0


def _compose_task_description(item: TaskBreakdownItem) -> str | None:
    """Merge structured fields into one markdown description for the coder agent."""
    sections: list[str] = []
    summary = item.description.strip()
    if summary:
        sections.append(f"## Objective\n{summary}")
    if item.plan_reference.strip():
        sections.append(f"## Plan reference\n{item.plan_reference.strip()}")
    if item.files_hint:
        lines = "\n".join(f"- `{path.strip()}`" for path in item.files_hint if path.strip())
        if lines:
            sections.append(f"## Suggested files / modules\n{lines}")
    if item.acceptance_criteria:
        lines = "\n".join(
            f"- {criterion.strip()}" for criterion in item.acceptance_criteria if criterion.strip()
        )
        if lines:
            sections.append(f"## Acceptance criteria\n{lines}")
    text = "\n\n".join(sections).strip()
    return text if text else None


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
        "You are a project planning assistant. Read the approved PLAN.md and extract concrete "
        "engineering tasks for a Kanban board. Each task will be executed by an autonomous coding agent "
        "that only sees the task title and description — make descriptions self-contained and actionable.\n\n"
        "Reply with **only** valid JSON: either a top-level array, or an object "
        '`{"tasks": [...]}` where each element has:\n'
        '- "title" (string, required, max 120 chars; verb-first, specific, e.g. "Add JWT login endpoint")\n'
        '- "description" (string, required, 2–6 sentences: scope, approach, constraints, what NOT to change)\n'
        '- "acceptance_criteria" (array of strings, required, 2–5 testable bullet points)\n'
        '- "plan_reference" (string, required; quote or paraphrase the PLAN section this task implements)\n'
        '- "files_hint" (array of strings, optional; likely file paths or modules, e.g. "backend/app/routers/auth.py")\n'
        '- "priority" (integer; lower = higher urgency; default 0)\n\n'
        "Rules:\n"
        "- Produce 3–40 tasks when the PLAN is substantial; fewer if the PLAN is tiny.\n"
        "- Do NOT create meta tasks (writing docs, creating plans, running reviews only).\n"
        "- Split large PLAN items into independently implementable units.\n"
        "- Every task MUST have a non-empty description and at least 2 acceptance criteria.\n"
        "- Order tasks so dependencies come first (models before API, API before UI).\n"
    )
    human = f"## Approved PLAN\n\n{plan_markdown}\n"

    require_llm_configured(settings.architect_llm_provider)
    llm = create_architect_llm(temperature=0.1)
    llm_response = await ainvoke_llm(
        llm,
        [SystemMessage(content=system), HumanMessage(content=human)],
    )
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
        desc = _compose_task_description(it)
        if not desc:
            logger.warning("Skipping task with empty composed description: %s", title)
            continue
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
