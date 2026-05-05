"""
LangGraph: 2-node graph (planner LLM -> worker LLM) via Groq.
Run: set GROQ_API_KEY, then python demo_langgraph.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TypedDict

_EVAL = Path(__file__).resolve().parents[1]
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))
from load_repo_env import load_repo_env

load_repo_env()

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph


class DemoState(TypedDict):
    numbers: str
    plan: str
    answer: str


def _require_groq() -> None:
    if not os.getenv("GROQ_API_KEY"):
        print("Set GROQ_API_KEY in the environment.", file=sys.stderr)
        sys.exit(1)


def node_planner(state: DemoState) -> dict[str, str]:
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    msg = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are Planner. In one short sentence, say how you will compute "
                    "the sum of the given integers."
                )
            ),
            HumanMessage(content=f"Numbers: {state['numbers']}"),
        ]
    )
    return {"plan": str(msg.content)}


def node_worker(state: DemoState) -> dict[str, str]:
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    msg = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are Worker. Compute the exact integer sum. "
                    "Reply in one line: SUM: <integer>"
                )
            ),
            HumanMessage(
                content=f"Numbers: {state['numbers']}\nPlanner said: {state['plan']}"
            ),
        ]
    )
    return {"answer": str(msg.content)}


def main() -> None:
    _require_groq()
    numbers = "3, 5, 7, 11"
    builder = StateGraph(DemoState)
    builder.add_node("planner", node_planner)
    builder.add_node("worker", node_worker)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "worker")
    builder.add_edge("worker", END)
    graph = builder.compile()
    out = graph.invoke({"numbers": numbers, "plan": "", "answer": ""})
    print("--- LangGraph demo ---")
    print("numbers:", out["numbers"])
    print("plan:", out["plan"])
    print("answer:", out["answer"])
    expected = sum(int(x.strip()) for x in numbers.replace(",", " ").split() if x.strip())
    print("expected sum:", expected)


if __name__ == "__main__":
    main()
