"""Executor: ReAct-style tool-calling agent for direct board mutations.

Stays small: at most ``max_steps`` tool calls, each step issued by the LLM via
LangChain ``bind_tools``. If LLM is unavailable or refuses to call tools, the
node returns whatever was done so far.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool


_SYSTEM = (
    "You are the Executor agent. You can mutate a Kanban board through tools. "
    "Use tools to fulfill the user's request. Prefer the minimum number of tool calls. "
    "When you are done, respond with a short confirmation in plain text."
)
_VI_EXEC = (
    " The user writes in Vietnamese: interpret their intent and reply in Vietnamese in the final message."
)


def _make_lc_tools(handler_factory: Callable[[str], Callable[..., Any]]):
    """Return LangChain tool wrappers backed by async handlers via a sync facade.

    The actual async DB calls happen in `agent_runner` which intercepts
    LangChain's ``ToolMessage`` flow; here we just expose declarations.
    """

    @tool("create_task", parse_docstring=False)
    def create_task(title: str, description: str = "", priority: str = "medium",
                    column_id: str = "", est_hours: float | None = None) -> str:
        """Create a task on the current board."""
        return handler_factory("create_task")(
            title=title, description=description, priority=priority,
            column_id=column_id or None, est_hours=est_hours,
        )

    @tool("update_task_status", parse_docstring=False)
    def update_task_status(task_id: str, column_id: str) -> str:
        """Move a task to another column (status auto-derived from column name)."""
        return handler_factory("update_task_status")(task_id=task_id, column_id=column_id)

    @tool("assign_task", parse_docstring=False)
    def assign_task(task_id: str, user_id: str) -> str:
        """Assign a user to a task."""
        return handler_factory("assign_task")(task_id=task_id, user_id=user_id)

    @tool("query_tasks", parse_docstring=False)
    def query_tasks(column_id: str = "", status: str = "", limit: int = 50) -> str:
        """List tasks; filter by column_id or status."""
        return handler_factory("query_tasks")(
            column_id=column_id or None, status=status or None, limit=limit,
        )

    return [create_task, update_task_status, assign_task, query_tasks]


def execute(
    llm,
    user_message: str,
    *,
    sync_handler_factory: Callable[[str], Callable[..., Any]],
    on_tool_event: Callable[[str, dict[str, Any], Any], None] | None = None,
    max_steps: int = 5,
    locale: str = "en",
) -> dict[str, Any]:
    tools = _make_lc_tools(sync_handler_factory)
    try:
        bound = llm.bind_tools(tools)
    except Exception:
        return {"final": "Tool calling unavailable.", "tool_calls": []}

    sys_content = _SYSTEM + (_VI_EXEC if (locale or "en").lower().startswith("vi") else "")
    messages: list[BaseMessage] = [
        SystemMessage(content=sys_content),
        HumanMessage(content=user_message),
    ]
    tool_calls_log: list[dict[str, Any]] = []

    for step in range(max_steps):
        try:
            ai_msg: AIMessage = bound.invoke(messages)
        except Exception as e:
            return {"final": f"LLM error: {e}", "tool_calls": tool_calls_log}
        messages.append(ai_msg)
        tcalls = getattr(ai_msg, "tool_calls", None) or []
        if not tcalls:
            return {"final": str(ai_msg.content or ""), "tool_calls": tool_calls_log}

        for tc in tcalls:
            name = tc.get("name") or tc.get("function", {}).get("name")
            args = tc.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            try:
                handler = sync_handler_factory(name)
                result = handler(**args)
                ok = True
            except Exception as e:
                result = {"error": str(e)}
                ok = False
            tool_calls_log.append({"tool": name, "args": args, "ok": ok, "result": result})
            if on_tool_event:
                try:
                    on_tool_event(name, args, result)
                except Exception:
                    pass
            messages.append(
                ToolMessage(
                    content=json.dumps(result, default=str)[:4000],
                    tool_call_id=tc.get("id", name),
                )
            )

    return {"final": "Stopped: max_steps reached.", "tool_calls": tool_calls_log}
