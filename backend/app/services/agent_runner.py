"""Run the multi-agent graph for one ``AgentRun``.

Uses LangGraph at the supervisor level to make the hierarchical
Orchestrator → Worker pattern explicit. Worker nodes wrap the pure-logic
agent functions in ``agents/src/agents/*`` and bind them to a per-run
``ToolContext`` (DB session) plus a step callback that:

1. Inserts an ``AgentRunStep`` row,
2. Pushes a ``run.step`` WebSocket event.

LLM token usage is captured via LangChain ``UsageMetadataCallbackHandler``
when available; cost is estimated from `services.llm.estimate_cost`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from agents.src.agents.orchestrator import IntentDecision, classify
from agents.src.agents.planner import plan_goal
from agents.src.agents.assigner import suggest_assignee
from agents.src.agents.monitor import detect_bottlenecks
from agents.src.agents.reporter import make_report
from agents.src.agents.executor import execute as executor_run
from app.config import settings
from app.models import AgentRun, AgentRunStep
from app.services.llm import estimate_cost, get_chat_model, model_id_of
from app.services.tool_handlers import HANDLERS, ToolContext, list_board_members
from app.services.ws_manager import push_event, topic_board, topic_run

log = logging.getLogger(__name__)


class RunInput(TypedDict, total=False):
    intent_hint: Optional[str]
    user_message: str
    target_column_id: Optional[str]
    task_id: Optional[str]
    since: Optional[str]
    until: Optional[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _record_step(
    db: AsyncSession,
    run_id: uuid.UUID,
    step_index: int,
    node: str,
    *,
    input_summary: str,
    output_summary: str,
    payload: dict[str, Any] | None,
    latency_ms: int,
) -> None:
    step = AgentRunStep(
        run_id=run_id,
        step_index=step_index,
        node=node,
        input_summary=input_summary[:4000],
        output_summary=output_summary[:4000],
        payload=payload,
        latency_ms=latency_ms,
        finished_at=datetime.now(timezone.utc),
    )
    db.add(step)
    await db.commit()


async def _emit_step(
    run_id: uuid.UUID, board_id: uuid.UUID, step_index: int, node: str, status: str, **extra: Any
) -> None:
    await push_event(
        topic_run(str(run_id)),
        {
            "type": "run.step",
            "run_id": str(run_id),
            "step_index": step_index,
            "node": node,
            "status": status,
            **extra,
        },
    )


def _summarize(value: Any, limit: int = 220) -> str:
    try:
        s = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        s = str(value)
    return s[:limit]


async def _gather_board_snapshot(ctx: ToolContext) -> dict[str, Any]:
    from app.services.tool_handlers import (
        query_tasks as _query_tasks,
        get_board_activity as _board_activity,
    )
    tasks = (await _query_tasks(ctx, limit=200)).get("tasks", [])
    activity = (await _board_activity(ctx, limit=100)).get("events", [])
    return {"tasks": tasks, "activity": activity}


async def run_agent(
    *,
    db: AsyncSession,
    actor_id: uuid.UUID,
    board_id: uuid.UUID,
    intent_hint: Optional[str],
    user_message: str,
    extra: Optional[RunInput] = None,
) -> AgentRun:
    """Create an AgentRun, execute the graph, persist and return it."""
    extra = extra or {}
    run = AgentRun(
        board_id=board_id,
        actor_id=actor_id,
        intent=intent_hint or "auto",
        status="running",
        user_message=user_message,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await push_event(
        topic_run(str(run.id)),
        {"type": "run.started", "run_id": str(run.id), "intent": run.intent, "started_at": _now_iso()},
    )
    started_at = time.time()

    ctx = ToolContext(db=db, actor_id=actor_id, board_id=board_id)
    step_index = 0
    tokens_in = 0
    tokens_out = 0
    cost = 0.0
    final_intent = intent_hint or "auto"
    result: dict[str, Any] = {}
    error: Optional[str] = None
    locale = str((extra.get("context") or {}).get("locale") or extra.get("locale") or "vi").strip().lower()

    try:
        # === Step 0: Orchestrator (intent classification) ===
        t0 = time.time()
        orch_llm = get_chat_model(settings.llm_orchestrator_model)
        decision: IntentDecision = await asyncio.to_thread(
            classify, orch_llm, user_message, intent_hint, locale=locale
        )
        final_intent = decision.intent
        latency = int((time.time() - t0) * 1000)
        await _emit_step(run.id, board_id, step_index, "orchestrator", "finished",
                         output_summary=f"intent={decision.intent}", latency_ms=latency)
        await _record_step(
            db, run.id, step_index, "orchestrator",
            input_summary=user_message,
            output_summary=f"intent={decision.intent} reason={decision.reason}",
            payload={"intent": decision.intent, "reason": decision.reason},
            latency_ms=latency,
        )
        step_index += 1

        # === Step 1: Worker ===
        if decision.intent == "plan":
            await _emit_step(run.id, board_id, step_index, "planner", "started")
            t0 = time.time()
            from app.services.tool_handlers import search_similar_tasks as _sst
            similar = (await _sst(ctx, query=user_message, top_k=5)).get("matches", [])
            llm = get_chat_model(settings.llm_planner_model)
            plan = await asyncio.to_thread(plan_goal, llm, user_message, similar, locale=locale)
            payload = plan.model_dump()
            result = {"plan": payload}
            latency = int((time.time() - t0) * 1000)
            await _emit_step(run.id, board_id, step_index, "planner", "finished",
                             output_summary=f"{len(plan.subtasks)} subtasks", latency_ms=latency)
            await _record_step(db, run.id, step_index, "planner",
                               input_summary=user_message,
                               output_summary=f"{len(plan.subtasks)} subtasks",
                               payload=payload, latency_ms=latency)
            cost += estimate_cost(model_id_of(settings.llm_planner_model), 800, 600)
            step_index += 1

        elif decision.intent == "assign":
            await _emit_step(run.id, board_id, step_index, "assigner", "started")
            t0 = time.time()
            from app.services.tool_handlers import (
                query_tasks as _qt,
                get_user_skills as _gus,
                get_user_workload as _guw,
            )
            tasks = (await _qt(ctx, limit=200)).get("tasks", [])
            context = (extra or {}).get("context") or {}
            task_index = context.get("task_index") if isinstance(context, dict) else None
            task_id = (extra or {}).get("task_id") or _extract_uuid(user_message)
            if not task_id:
                task_id = _resolve_task_id_from_message(user_message, tasks, task_index=task_index)
            if not task_id:
                raise ValueError(
                    "Không xác định được task cần gán. Hãy nêu rõ tên task (ví dụ: 'gán task AI cho ai?') "
                    "hoặc gửi task_id."
                )
            target = next((t for t in tasks if t["id"] == task_id), None)
            if target is None:
                raise ValueError(f"Task {task_id} not found on this board")
            members = await list_board_members(ctx)
            candidates: list[dict[str, Any]] = []
            for m in members:
                skills = (await _gus(ctx, user_id=m["id"])).get("skills", [])
                workload = await _guw(ctx, user_id=m["id"], board_id=str(board_id))
                candidates.append({**m, "skills": skills, "workload": workload})
            llm = get_chat_model(settings.llm_assigner_model)
            assignment = await asyncio.to_thread(suggest_assignee, llm, target, candidates, locale)
            payload = assignment.model_dump()
            result = {"assignments": payload, "task": target}
            latency = int((time.time() - t0) * 1000)
            await _emit_step(run.id, board_id, step_index, "assigner", "finished",
                             output_summary=f"{len(assignment.suggestions)} candidates", latency_ms=latency)
            await _record_step(db, run.id, step_index, "assigner",
                               input_summary=f"task={target.get('title')}",
                               output_summary=f"{len(assignment.suggestions)} suggestions",
                               payload=payload, latency_ms=latency)
            cost += estimate_cost(model_id_of(settings.llm_assigner_model), 600, 400)
            step_index += 1

        elif decision.intent == "monitor":
            await _emit_step(run.id, board_id, step_index, "monitor", "started")
            t0 = time.time()
            snap = await _gather_board_snapshot(ctx)
            from sqlalchemy import select
            from app.models import Column as ColumnModel
            cols_res = await db.execute(select(ColumnModel).where(ColumnModel.board_id == board_id))
            cols = [
                {"id": str(c.id), "name": c.name, "wip_limit": c.wip_limit, "position": c.position}
                for c in cols_res.scalars().all()
            ]
            llm = get_chat_model(settings.llm_monitor_model)
            mon = await asyncio.to_thread(
                detect_bottlenecks, llm, columns=cols, tasks=snap["tasks"], activity=snap["activity"], locale=locale
            )
            payload = mon.model_dump()
            result = {"alerts": payload["alerts"], "summary": payload["summary"]}
            latency = int((time.time() - t0) * 1000)
            await _emit_step(run.id, board_id, step_index, "monitor", "finished",
                             output_summary=f"{len(mon.alerts)} alerts", latency_ms=latency)
            await _record_step(db, run.id, step_index, "monitor",
                               input_summary=f"{len(snap['tasks'])} tasks",
                               output_summary=f"{len(mon.alerts)} alerts",
                               payload=payload, latency_ms=latency)
            cost += estimate_cost(model_id_of(settings.llm_monitor_model), 600, 200)
            step_index += 1

        elif decision.intent == "report":
            await _emit_step(run.id, board_id, step_index, "reporter", "started")
            t0 = time.time()
            snap = await _gather_board_snapshot(ctx)
            members = await list_board_members(ctx)
            llm = get_chat_model(settings.llm_reporter_model)
            md = await asyncio.to_thread(
                make_report,
                llm,
                period="recent",
                tasks=snap["tasks"],
                activity=snap["activity"],
                members=members,
                locale=locale,
                user_question=user_message,
            )
            result = {"report_md": md}
            latency = int((time.time() - t0) * 1000)
            await _emit_step(run.id, board_id, step_index, "reporter", "finished",
                             output_summary=f"{len(md)} chars", latency_ms=latency)
            await _record_step(db, run.id, step_index, "reporter",
                               input_summary=f"{len(snap['tasks'])} tasks, {len(snap['activity'])} events",
                               output_summary=md[:200],
                               payload={"report_md": md}, latency_ms=latency)
            cost += estimate_cost(model_id_of(settings.llm_reporter_model), 1200, 600)
            step_index += 1

        elif decision.intent == "execute":
            await _emit_step(run.id, board_id, step_index, "executor", "started")
            t0 = time.time()
            llm = get_chat_model(settings.llm_executor_model)

            def _factory(name: str):
                handler = HANDLERS.get(name)
                if handler is None:
                    raise ValueError(f"Unknown tool {name}")
                # Async handler -> sync facade
                def _call(**kwargs):
                    return asyncio.run_coroutine_threadsafe(
                        handler(ctx, **kwargs), _LOOP
                    ).result()
                return _call

            def _on_tool(name: str, args: dict[str, Any], res: Any) -> None:
                asyncio.run_coroutine_threadsafe(
                    push_event(
                        topic_run(str(run.id)),
                        {"type": "run.tool", "run_id": str(run.id), "node": "executor",
                         "tool": name, "args": args, "result": res},
                    ),
                    _LOOP,
                )

            exec_out = await asyncio.to_thread(
                executor_run,
                llm,
                user_message,
                sync_handler_factory=_factory,
                on_tool_event=_on_tool,
                max_steps=settings.agent_max_tool_calls,
                locale=locale,
            )
            result = {"executor": exec_out}
            latency = int((time.time() - t0) * 1000)
            await _emit_step(run.id, board_id, step_index, "executor", "finished",
                             output_summary=f"{len(exec_out.get('tool_calls', []))} tool calls",
                             latency_ms=latency)
            await _record_step(db, run.id, step_index, "executor",
                               input_summary=user_message[:200],
                               output_summary=str(exec_out.get("final", ""))[:200],
                               payload=exec_out, latency_ms=latency)
            cost += estimate_cost(model_id_of(settings.llm_executor_model), 800, 400)
            # Notify board listeners that something likely changed
            await push_event(topic_board(str(board_id)),
                             {"type": "board.changed", "board_id": str(board_id), "kind": "agent.execute"})
            step_index += 1

        else:
            # Pure greeting only — helpful tips in user's language
            if locale.startswith("vi"):
                result = {
                    "message": (
                        "Xin chào! Mình có thể giúp bạn trên board này:\n\n"
                        "• **Tách task / lên kế hoạch**: ví dụ *«Phân rã mục tiêu triển khai đăng nhập JWT»*\n"
                        "• **Gán người**: *«Gợi ý ai làm task [tên task]»* (hoặc dán UUID task)\n"
                        "• **Tắc nghẽn**: *«Board có chỗ nào bị nghẽn không?»*\n"
                        "• **Tóm tắt / hỏi đáp**: *«Tóm tắt tình hình board»* hoặc hỏi cụ thể về task\n"
                        "• **Thao tác**: *«Tạo task …»*, *«Đổi cột …»*\n\n"
                        "Hãy gõ câu hỏi hoặc yêu cầu cụ thể bằng tiếng Việt nhé."
                    ),
                    "report_md": None,
                }
            else:
                result = {
                    "message": (
                        "Hi! I can help with this board:\n\n"
                        "• **Plan / breakdown**: e.g. *Break down the login JWT goal*\n"
                        "• **Assign**: *Who should own task X?*\n"
                        "• **Monitor**: *Any bottlenecks?*\n"
                        "• **Report / Q&A**: *Summarize the board* or ask about specific tasks\n"
                        "• **Execute**: *Create task …*, *Move …*\n"
                    ),
                    "report_md": None,
                }
            await _emit_step(run.id, board_id, step_index, "orchestrator", "finished",
                             output_summary="end_greeting", latency_ms=0)

    except Exception as e:  # pragma: no cover
        log.exception("Agent run failed: %s", e)
        error = str(e)
        await push_event(
            topic_run(str(run.id)),
            {"type": "run.error", "run_id": str(run.id), "error": error, "recoverable": False},
        )

    # Persist final run state
    run.status = "error" if error else "done"
    run.intent = final_intent
    run.result = result
    run.error = error
    run.tokens_in = int(tokens_in)
    run.tokens_out = int(tokens_out)
    run.cost_usd = round(float(cost), 6)
    run.latency_ms = int((time.time() - started_at) * 1000)
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)

    await push_event(
        topic_run(str(run.id)),
        {
            "type": "run.finished",
            "run_id": str(run.id),
            "status": run.status,
            "latency_ms": run.latency_ms,
            "tokens_in": run.tokens_in,
            "tokens_out": run.tokens_out,
            "cost_usd": run.cost_usd,
            "result": result,
            "error": error,
        },
    )
    return run


def _extract_uuid(text: str) -> Optional[str]:
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text or "")
    return m.group(0) if m else None


def _resolve_task_id_from_message(
    text: str,
    tasks: list[dict[str, Any]],
    *,
    task_index: dict[str, Any] | None = None,
) -> Optional[str]:
    msg = (text or "").strip().lower()
    if not msg:
        return None

    # 0) Task index map (preferred for "task 0", "#2", ...)
    idx_match = re.search(r"(?:task|công việc|cv|#|id)\s*([0-9]{1,3})", msg)
    if idx_match:
        idx = idx_match.group(1)
        if isinstance(task_index, dict):
            hit = task_index.get(idx)
            if isinstance(hit, str) and hit:
                return hit
        try:
            i = int(idx)
            if 0 <= i < len(tasks):
                return str(tasks[i].get("id"))
        except ValueError:
            pass

    # 1) Direct title substring match (preferred)
    direct: list[str] = []
    for t in tasks:
        title = str(t.get("title") or "").strip()
        if not title:
            continue
        if title.lower() in msg:
            direct.append(str(t.get("id")))
    if len(direct) == 1:
        return direct[0]

    # 2) Token overlap score fallback
    stop = {"task", "viec", "việc", "cho", "ai", "can", "cần", "gan", "gán", "nguoi", "người"}
    msg_tokens = {w for w in re.findall(r"\w+", msg) if len(w) >= 2 and w not in stop}
    best_id: Optional[str] = None
    best_score = 0
    tie = False
    for t in tasks:
        title = str(t.get("title") or "").lower()
        title_tokens = {w for w in re.findall(r"\w+", title) if len(w) >= 2}
        if not title_tokens:
            continue
        score = len(msg_tokens & title_tokens)
        if score > best_score:
            best_score = score
            best_id = str(t.get("id"))
            tie = False
        elif score and score == best_score:
            tie = True
    if best_score > 0 and not tie:
        return best_id
    return None


# Cached event loop reference for thread-safe schedule-from-thread.
_LOOP: asyncio.AbstractEventLoop | None = None


def install_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _LOOP
    _LOOP = loop
