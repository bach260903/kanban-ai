"""LangGraph agent workflow skeleton with Postgres checkpointing (T035)."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

# ``coder_node`` is implemented for US8 / T058. ``task_breakdown`` runs after ``plan`` when the graph
# continues past PLAN HIL (or via ``run_task_breakdown_task`` on PLAN approve — US7 / T048).
from app.agent.nodes import coder_node, plan_node, spec_node, task_breakdown_node


def _route_after_spec(state: dict[str, Any]) -> str:
    """HIL / error routing after SPEC (skeleton — full resume wiring in later tasks)."""
    if state.get("error"):
        return END
    if str(state.get("feedback", "")).strip():
        return "spec"
    return "plan"


def _route_after_plan(state: dict[str, Any]) -> str:
    """After PLAN node: stop at HIL / errors (US7). Task breakdown runs on PLAN approve via REST."""
    if state.get("error"):
        return END
    if state.get("run_task_breakdown_after_plan"):
        return "task_breakdown"
    return END


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
    workflow.add_conditional_edges(
        "plan",
        _route_after_plan,
        {"task_breakdown": "task_breakdown", END: END},
    )
    # TASK_BREAKDOWN → IDLE (no automatic coder hand-off until US8 / T058).
    workflow.add_edge("task_breakdown", END)
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
