"""Planner: turn a goal into structured subtasks."""
from __future__ import annotations

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=1000)
    est_hours: float = Field(default=2.0, ge=0.0, le=200.0)
    required_skills: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    subtasks: list[SubTask] = Field(default_factory=list, max_length=12)
    notes: str = Field(default="")


_SYSTEM = (
    "You are a senior project planner for a software team using a Kanban board. "
    "Break the user's goal into 3-8 concrete, independent subtasks that can be assigned. "
    "Each subtask must have a clear title (≤120 chars), short description, est_hours (1-16 typical), "
    "required_skills (lowercase tags like 'fastapi', 'react', 'sql'), and depends_on (titles of earlier subtasks if any). "
    "Avoid vague subtasks like 'Setup project' or 'Plan the work'. "
    "Reply with JSON only."
)

_VI_EXTRA = (
    " If the user's goal is in Vietnamese, write each subtask title, description, and notes in Vietnamese "
    "(keep required_skills as short English slugs for consistency)."
)


def plan_goal(
    llm,
    goal_text: str,
    similar_examples: Optional[list[dict]] = None,
    *,
    locale: str = "en",
) -> Plan:
    system = _SYSTEM + (_VI_EXTRA if (locale or "en").lower().startswith("vi") else "")
    examples_block = ""
    if similar_examples:
        bullets = "\n".join(f"- {ex.get('snippet', '')[:160]}" for ex in similar_examples[:5] if ex)
        if bullets:
            examples_block = (
                "\nFor reference, here are similar past tasks from this board (do NOT copy verbatim):\n"
                + bullets
            )
    user = f"Goal: {goal_text}{examples_block}"
    try:
        structured = llm.with_structured_output(Plan)
        out = structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        if isinstance(out, Plan):
            return out
        if isinstance(out, dict):
            return Plan(**out)
    except Exception:
        pass
    # Fallback minimal plan
    return Plan(
        subtasks=[
            SubTask(title=f"Investigate scope of: {goal_text[:80]}", est_hours=2.0),
            SubTask(title="Implement core change", est_hours=4.0),
            SubTask(title="Write tests + docs", est_hours=2.0),
        ],
        notes="Fallback plan (LLM unavailable).",
    )
