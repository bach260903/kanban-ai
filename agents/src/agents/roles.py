"""Role identifiers used as LangGraph node names.

Keeping them as constants avoids typos when wiring `add_conditional_edges` and
`StateGraph.add_node` calls in `agents/src/graph.py`.
"""
from __future__ import annotations

NODE_ORCHESTRATOR = "orchestrator"
NODE_PLANNER = "planner"
NODE_ASSIGNER = "assigner"
NODE_MONITOR = "monitor"
NODE_REPORTER = "reporter"
NODE_EXECUTOR = "executor"

ALL_NODES = (
    NODE_ORCHESTRATOR,
    NODE_PLANNER,
    NODE_ASSIGNER,
    NODE_MONITOR,
    NODE_REPORTER,
    NODE_EXECUTOR,
)
