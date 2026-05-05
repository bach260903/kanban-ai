"""LangGraph builder skeleton (Phase 2 deliverable).

Phase 3 will replace the stub `_node_*` callables with real LLM-backed logic
and tool calls. This file already wires the supervisor → worker hierarchy so
that the graph compiles and `astream_events` can be exercised end-to-end with
no-op nodes.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.src.agents.roles import (
    NODE_ASSIGNER,
    NODE_EXECUTOR,
    NODE_MONITOR,
    NODE_ORCHESTRATOR,
    NODE_PLANNER,
    NODE_REPORTER,
)
from agents.src.state import MAX_ITERS, AgentState, Intent


def _node_orchestrator(state: AgentState) -> dict[str, Any]:
    """Stub: route based on a hint in `user_message`. Phase 3 will use an LLM."""
    iter_count = int(state.get("iter_count") or 0) + 1
    if iter_count >= MAX_ITERS:
        return {"intent": "end", "iter_count": iter_count}

    msg = (state.get("user_message") or "").lower()
    intent: Intent = "end"
    if any(k in msg for k in ("breakdown", "tách", "subtask", "plan")):
        intent = "plan"
    elif any(k in msg for k in ("assign", "gán", "ai làm")):
        intent = "assign"
    elif any(k in msg for k in ("bottleneck", "monitor", "tắc")):
        intent = "monitor"
    elif any(k in msg for k in ("report", "tóm tắt", "summary")):
        intent = "report"
    elif any(k in msg for k in ("create task", "tạo task", "move", "đổi cột")):
        intent = "execute"
    return {"intent": intent, "iter_count": iter_count}


def _passthrough_node(name: str):
    def _node(_state: AgentState) -> dict[str, Any]:
        return {"intent": "end"}

    _node.__name__ = f"_node_{name}"
    return _node


def _route(state: AgentState) -> str:
    intent = state.get("intent") or "end"
    if intent == "end":
        return END
    return {
        "plan": NODE_PLANNER,
        "assign": NODE_ASSIGNER,
        "monitor": NODE_MONITOR,
        "report": NODE_REPORTER,
        "execute": NODE_EXECUTOR,
    }[intent]


def build_graph():
    """Assemble the supervisor-worker LangGraph and compile it."""
    builder = StateGraph(AgentState)
    builder.add_node(NODE_ORCHESTRATOR, _node_orchestrator)
    builder.add_node(NODE_PLANNER, _passthrough_node(NODE_PLANNER))
    builder.add_node(NODE_ASSIGNER, _passthrough_node(NODE_ASSIGNER))
    builder.add_node(NODE_MONITOR, _passthrough_node(NODE_MONITOR))
    builder.add_node(NODE_REPORTER, _passthrough_node(NODE_REPORTER))
    builder.add_node(NODE_EXECUTOR, _passthrough_node(NODE_EXECUTOR))

    builder.add_edge(START, NODE_ORCHESTRATOR)
    builder.add_conditional_edges(
        NODE_ORCHESTRATOR,
        _route,
        {
            NODE_PLANNER: NODE_PLANNER,
            NODE_ASSIGNER: NODE_ASSIGNER,
            NODE_MONITOR: NODE_MONITOR,
            NODE_REPORTER: NODE_REPORTER,
            NODE_EXECUTOR: NODE_EXECUTOR,
            END: END,
        },
    )
    for worker in (NODE_PLANNER, NODE_ASSIGNER, NODE_MONITOR, NODE_REPORTER, NODE_EXECUTOR):
        builder.add_edge(worker, NODE_ORCHESTRATOR)

    return builder.compile()


__all__ = ["build_graph"]
