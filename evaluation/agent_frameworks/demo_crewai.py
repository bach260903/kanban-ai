"""
CrewAI: 2 agents (Planner + Worker) on the same numeric task via Groq/LiteLLM.
Run: set GROQ_API_KEY, then python demo_crewai.py

Requires Python 3.10–3.13 for current CrewAI wheels. On 3.14 use: py -3.12 -m venv .venv
"""
from __future__ import annotations

import os
import sys

from pathlib import Path

_EVAL = Path(__file__).resolve().parents[1]
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))
from load_repo_env import load_repo_env

load_repo_env()

if sys.version_info >= (3, 14):
    print(
        "CrewAI (modern) does not publish wheels for Python 3.14 yet.\n"
        "Use Python 3.12 or 3.13, e.g.:\n"
        "  py -3.12 -m venv .venv-crewai\n"
        "  .\\.venv-crewai\\Scripts\\activate\n"
        "  pip install -r requirements-crewai.txt\n"
        "See README.md in this folder.",
        file=sys.stderr,
    )
    sys.exit(1)

from crewai import Agent, Crew, LLM, Process, Task


def _require_groq() -> None:
    if not os.getenv("GROQ_API_KEY"):
        print("Set GROQ_API_KEY in the environment.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    _require_groq()
    numbers = "3, 5, 7, 11"
    llm = LLM(model="groq/llama-3.3-70b-versatile", api_key=os.environ["GROQ_API_KEY"])

    planner = Agent(
        role="Planner",
        goal="Propose a clear plan to sum the given integers.",
        backstory="You reason briefly before any calculation.",
        llm=llm,
        verbose=False,
    )
    worker = Agent(
        role="Worker",
        goal="Compute the exact integer sum and state it as SUM: <integer>.",
        backstory="You only calculate; you trust the list of numbers given in the task.",
        llm=llm,
        verbose=False,
    )

    task1 = Task(
        description=f"Numbers: {numbers}. Write one sentence plan to sum them.",
        expected_output="One short sentence.",
        agent=planner,
    )
    task2 = Task(
        description=(
            f"Numbers: {numbers}. Using the plan from the previous task, output one line: "
            "SUM: <integer>"
        ),
        expected_output="One line starting with SUM:",
        agent=worker,
        context=[task1],
    )

    crew = Crew(agents=[planner, worker], tasks=[task1, task2], process=Process.sequential)
    result = crew.kickoff()
    print("--- CrewAI demo ---")
    print(result)


if __name__ == "__main__":
    main()
