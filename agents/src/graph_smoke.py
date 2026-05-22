"""Phase 2 smoke test: build and invoke the skeleton graph without any LLM.

Run from repo root:

    python -m agents.src.graph_smoke

Expected: prints 5 routing scenarios and the registered tool names.
"""
from __future__ import annotations

from agents.src.graph import build_graph
from agents.src.tools import TOOL_REGISTRY


SCENARIOS: list[tuple[str, str]] = [
    ("plan",    "Please breakdown the login feature into subtasks"),
    ("assign",  "Who should I assign this task to?"),
    ("monitor", "Any bottleneck on the board?"),
    ("report",  "Give me a weekly summary"),
    ("execute", "Create task 'Review PR' in this board"),
]


def main() -> None:
    graph = build_graph()
    print("Tools registered:", sorted(TOOL_REGISTRY.keys()))
    for label, msg in SCENARIOS:
        out = graph.invoke({"user_message": msg, "board_id": "demo", "user_id": "demo"})
        intent = out.get("intent")
        iter_count = out.get("iter_count")
        print(f"[{label:>8}] -> first_intent_seen={'plan' if label=='plan' else label} | final={intent} iter={iter_count}")


if __name__ == "__main__":
    main()
