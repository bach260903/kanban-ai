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


def _salvage_task_objects(text: str) -> list[Any]:
    """Recover complete ``{...}`` task objects from malformed/truncated JSON.

    LLMs sometimes return a long task array that gets cut off mid-object (token
    limit) or wrapped in reasoning text. Rather than failing the whole breakdown,
    scan from the first ``[`` and extract every balanced object that parses — the
    incomplete trailing one is simply dropped.
    """
    bracket = text.find("[")
    scan = text[bracket + 1:] if bracket != -1 else text
    objs: list[Any] = []
    depth = 0
    start: int | None = None
    in_str = False
    esc = False
    for i, ch in enumerate(scan):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        objs.append(json.loads(scan[start:i + 1]))
                    except json.JSONDecodeError:
                        pass
                    start = None
    return objs


_TEST_ONLY_RE = re.compile(
    r"^(write|add|create|implement)\s+(comprehensive\s+)?(unit\s+|integration\s+)?"
    r"(jest|pytest|vitest|tests?|test\s+suite|spec)\b",
    re.IGNORECASE,
)
_SETUP_ONLY_RE = re.compile(
    r"^(initialize|init|set\s*up|setup|scaffold|configure|bootstrap)\b",
    re.IGNORECASE,
)


def _post_process_tasks(items: list[TaskBreakdownItem]) -> list[TaskBreakdownItem]:
    """Code-level enforcement: remove tasks that violate breakdown rules.

    - Test-only tasks ("Write Jest tests for X") are folded into the first
      implementation task's acceptance criteria instead of living as a
      separate Kanban card.
    - Setup/init-only tasks ("Initialize project scaffold") are folded into
      the first implementation task if the list has other tasks; kept if
      it is the only task.
    """
    impl_tasks: list[TaskBreakdownItem] = []
    folded_criteria: list[str] = []
    folded_hints: list[str] = []

    for item in items:
        title = item.title.strip()
        if _TEST_ONLY_RE.match(title) or _SETUP_ONLY_RE.match(title):
            folded_criteria.extend(item.acceptance_criteria)
            folded_hints.extend(item.files_hint)
            logger.info("task_breakdown: folding standalone task %r into impl task", title)
        else:
            impl_tasks.append(item)

    if not impl_tasks:
        return items  # all tasks were setup/test — keep as-is to avoid empty list

    # Attach folded criteria/hints to the first implementation task
    if folded_criteria:
        impl_tasks[0].acceptance_criteria.extend(folded_criteria)
    if folded_hints:
        impl_tasks[0].files_hint.extend(
            h for h in folded_hints if h not in impl_tasks[0].files_hint
        )

    if len(items) != len(impl_tasks):
        logger.info(
            "task_breakdown: post-process merged %d task(s) → %d task(s)",
            len(items), len(impl_tasks),
        )
    return impl_tasks


def _parse_task_payload(raw: str) -> list[TaskBreakdownItem]:
    blob = _strip_json_fence(raw)
    items_raw: list[Any] | None = None
    try:
        data = json.loads(blob)
        if isinstance(data, list):
            items_raw = data
        elif isinstance(data, dict) and isinstance(data.get("tasks"), list):
            items_raw = data["tasks"]
    except json.JSONDecodeError:
        items_raw = None

    if items_raw is None:
        # Dirty or truncated output → salvage the complete task objects we can.
        salvaged = _salvage_task_objects(blob)
        if not salvaged:
            raise ValueError(
                "LLM output was not valid JSON and no task objects could be salvaged."
            )
        logger.warning(
            "task_breakdown: malformed JSON; salvaged %d complete task object(s)", len(salvaged)
        )
        items_raw = salvaged

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
        '- "description" (string, required, 2–3 concise sentences: scope, approach, what NOT to change)\n'
        '- "acceptance_criteria" (array of strings, required, 2–3 short testable bullet points)\n'
        '- "plan_reference" (string, required; short reference to the PLAN section — do NOT quote it in full)\n'
        '- "files_hint" (array of strings, optional; likely file paths or modules, e.g. "backend/app/routers/auth.py")\n'
        '- "priority" (integer; lower = higher urgency; default 0)\n\n'
        "Rules:\n"
        "- Task count = number of DISTINCT USER-FACING FEATURES in the PLAN, capped at 12.\n"
        "  A 'feature' is something the user asked for. Sub-steps, setup, config, and testing "
        "are NOT features — they are part of implementing a feature.\n"
        "  Count features in the PLAN, then map: 1 feature → 1 task. Merge when features "
        "share the same file or module. Always default to fewer tasks.\n"
        "- Each task MUST be a DISTINCT deliverable. Never create two tasks that touch the same "
        "module/file/feature — merge them into one.\n"
        "- The coding agent ALWAYS writes the implementation AND its unit tests together in the same "
        "task. Do NOT create a separate 'write tests for X' task — fold into the feature task.\n"
        "- Do NOT create meta/quality tasks (writing docs, creating plans, running reviews, linting). "
        "The CI pipeline runs lint/test/build automatically — these are NOT Kanban tasks.\n"
        "- Do NOT generate infrastructure or tooling setup tasks (CI/CD, bundler config, "
        "ESLint setup, npm publishing, GitHub Actions). These are pre-configured.\n"
        "- Do NOT create separate tasks for: project init, package.json setup, tsconfig, "
        ".gitignore, README. Fold these into the first feature task.\n"
        "- Split the PLAN by FEATURE/COMPONENT (a cohesive unit of behaviour), not by activity "
        "(implement / test / lint / setup). One feature = one task that ships code + tests.\n"
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
    items = _post_process_tasks(items)
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

    # ── Auto-suggest dependencies via AI (non-fatal) ──────────────────
    try:
        from app.services.dependency_service import ai_suggest_dependencies  # lazy import

        dep_result = await ai_suggest_dependencies(session, project_id)
        logger.info(
            "AI dependency suggestion completed: added=%s skipped=%s total_tasks=%s",
            dep_result["added"],
            dep_result["skipped"],
            dep_result["total_tasks"],
        )
    except Exception:
        logger.warning("AI dependency suggestion failed (non-fatal)", exc_info=True)

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
