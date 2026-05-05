"""
AutoGen (AgentChat): 2 assistant agents in a short round-robin via Groq OpenAI-compatible API.
Run: set GROQ_API_KEY, then python demo_autogen.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_EVAL = Path(__file__).resolve().parents[1]
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))
from load_repo_env import load_repo_env

load_repo_env()

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient


def _require_groq() -> None:
    if not os.getenv("GROQ_API_KEY"):
        print("Set GROQ_API_KEY in the environment.", file=sys.stderr)
        sys.exit(1)


async def main() -> None:
    _require_groq()
    numbers = "3, 5, 7, 11"
    model_client = OpenAIChatCompletionClient(
        # Groq model name can be provider-specific; pass model_info explicitly for AutoGen.
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": ModelFamily.UNKNOWN,
            "structured_output": True,
        },
    )

    planner = AssistantAgent(
        "planner",
        model_client=model_client,
        system_message=(
            "You are Planner. In your turn, give one sentence: how to sum the integers. "
            "Do not give the final number yet."
        ),
    )
    worker = AssistantAgent(
        "worker",
        model_client=model_client,
        system_message=(
            "You are Worker. In your turn, output exactly one line: SUM: <integer> "
            "for the numbers in the task."
        ),
    )

    team = RoundRobinGroupChat([planner, worker], max_turns=4)
    task = (
        f"We need the sum of these integers: {numbers}. "
        "Planner goes first, then Worker gives SUM: line."
    )
    stream = team.run_stream(task=task)
    await Console(stream)


if __name__ == "__main__":
    asyncio.run(main())
