"""LangGraph agent workflow skeleton with Postgres checkpointing (T035)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

# Nodes imported as stubs — see T044, T048, T058
from app.agent.nodes import coder_node, plan_node, spec_node, task_breakdown_node


def _route_after_spec(state: dict[str, Any]) -> str:
    """HIL / error routing after SPEC (skeleton — full resume wiring in later tasks)."""
    if state.get("error"):
        return END
    if str(state.get("feedback", "")).strip():
        return "spec"
    return "plan"


def build_state_graph() -> StateGraph:
    """Construct the uncompiled ``StateGraph`` (nodes + edges + conditional HIL stub)."""
    workflow: StateGraph[dict[str, Any]] = StateGraph(dict[str, Any])

    workflow.add_node("spec", spec_node.run)
    workflow.add_node("plan", plan_node.run)
    workflow.add_node("task_breakdown", task_breakdown_node.run)
    workflow.add_node("coder", coder_node.run)

    workflow.add_edge(START, "spec")
    workflow.add_conditional_edges(
        "spec",
        _route_after_spec,
        {"plan": "plan", "spec": "spec", END: END},
    )
    workflow.add_edge("plan", "task_breakdown")
    workflow.add_edge("task_breakdown", "coder")
    workflow.add_edge("coder", END)

    return workflow


def compile_agent_graph(checkpointer: Any) -> Any:
    """Compile the graph with an ``AsyncPostgresSaver`` checkpointer.

    Install extras: ``langgraph-checkpoint-postgres`` and ``psycopg[binary]`` (see ``requirements.txt``).
    Call ``await checkpointer.setup()`` once before the first ``ainvoke`` / ``astream``.

    Example::

        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from app.agent.graph import compile_agent_graph, postgres_checkpoint_dsn
        from app.config import settings

        dsn = postgres_checkpoint_dsn(settings.database_url)
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            await saver.setup()
            graph = compile_agent_graph(saver)
    """
    return build_state_graph().compile(checkpointer=checkpointer)


def postgres_checkpoint_dsn(database_url: str) -> str:
    """Normalize SQLAlchemy async URL to a psycopg-compatible DSN for LangGraph."""
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url.removeprefix("postgresql+asyncpg://")
    return database_url
