"""
Smoke test: latency + short completion for multiple providers (Giai đoạn 1.2).
Requires env vars depending on which backends you enable:

  GROQ_API_KEY   -> Llama on Groq (default on)
  OPENAI_API_KEY -> GPT-4o-mini (optional)
  ANTHROPIC_API_KEY -> Claude Haiku (optional, install anthropic)
  GOOGLE_API_KEY / GEMINI_API_KEY -> Gemini Flash (optional, install google-generativeai)

Usage:
  python llm_latency_smoke.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Load d:\kanban\.env (same as backend) so GROQ_API_KEY works without export
_EVAL = Path(__file__).resolve().parent.parent
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))
from load_repo_env import load_repo_env

load_repo_env()
from dataclasses import dataclass
from typing import Callable


@dataclass
class Result:
    name: str
    seconds: float
    text: str


def _time_call(name: str, fn: Callable[[], str]) -> Result:
    t0 = time.perf_counter()
    text = fn()
    dt = time.perf_counter() - t0
    return Result(name=name, seconds=dt, text=text.replace("\n", " ")[:200])


def run_groq() -> Result | None:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

    def fn() -> str:
        m = llm.invoke(
            [HumanMessage(content="Reply with exactly: PING_OK")]
        )
        return str(m.content)

    return _time_call("groq_llama-3.3-70b", fn)


def run_openai_mini() -> Result | None:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def fn() -> str:
        m = llm.invoke([HumanMessage(content="Reply with exactly: PING_OK")])
        return str(m.content)

    return _time_call("openai_gpt-4o-mini", fn)


def run_anthropic_haiku() -> Result | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        print("anthropic: pip install langchain-anthropic")
        return None
    from langchain_core.messages import HumanMessage

    llm = ChatAnthropic(model="claude-3-5-haiku-latest", temperature=0)

    def fn() -> str:
        m = llm.invoke([HumanMessage(content="Reply with exactly: PING_OK")])
        return str(m.content)

    return _time_call("anthropic_haiku", fn)


def run_gemini_flash() -> Result | None:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        print("gemini: pip install google-generativeai")
        return None

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    def fn() -> str:
        r = model.generate_content("Reply with exactly: PING_OK")
        return getattr(r, "text", str(r)) or ""

    return _time_call("gemini_flash", fn)


def main() -> None:
    runners = [run_groq, run_openai_mini, run_anthropic_haiku, run_gemini_flash]
    any_ok = False
    for rfn in runners:
        res = rfn()
        if res is None:
            continue
        any_ok = True
        print(f"{res.name}: {res.seconds:.3f}s | {res.text!r}")
    if not any_ok:
        print("No API keys set. Set at least GROQ_API_KEY.")


if __name__ == "__main__":
    main()
