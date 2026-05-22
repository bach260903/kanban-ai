"""Assigner: pick the best user for a task using skill match + workload."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class AssignmentSuggestion(BaseModel):
    user_id: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(max_length=400)


class AssignmentResult(BaseModel):
    suggestions: list[AssignmentSuggestion] = Field(default_factory=list, max_length=5)


_SYSTEM = (
    "You are the Assigner agent in a Kanban tool. "
    "Given a task and a list of candidate users (with their skills and current workload), "
    "rank the top 1-3 candidates. Higher score = better fit. "
    "Reasoning must mention skill match AND workload. "
    "Always return JSON of shape {\"suggestions\": [{user_id, score, reason}, ...]}."
)

_VI_REASON = " Write the \"reason\" field in Vietnamese if the task title or context is Vietnamese."


def suggest_assignee(
    llm,
    task: dict[str, Any],
    candidates: list[dict[str, Any]],
    locale: str = "en",
) -> AssignmentResult:
    if not candidates:
        return AssignmentResult(suggestions=[])

    # Heuristic baseline (still returned if LLM call fails)
    def _heuristic_score(c: dict[str, Any]) -> float:
        skills = {s["skill"].lower() for s in c.get("skills", [])}
        required = {(t or "").lower() for t in (task.get("required_skills") or task.get("tags") or [])}
        match = len(skills & required) / max(1, len(required) or 1)
        workload = c.get("workload") or {}
        open_tasks = int(workload.get("open_tasks", 0))
        load_penalty = 1.0 / (1.0 + open_tasks * 0.3)
        return round(min(1.0, match * 0.7 + load_penalty * 0.3), 4)

    fallback = AssignmentResult(
        suggestions=[
            AssignmentSuggestion(
                user_id=c["id"],
                score=_heuristic_score(c),
                reason=(
                    f"Heuristic: skills={[s['skill'] for s in c.get('skills', [])][:5]}, "
                    f"open_tasks={c.get('workload', {}).get('open_tasks', 0)}"
                ),
            )
            for c in candidates
        ]
    )
    fallback.suggestions.sort(key=lambda s: -s.score)
    fallback.suggestions = fallback.suggestions[:3]

    system = _SYSTEM + (_VI_REASON if (locale or "en").lower().startswith("vi") else "")
    try:
        structured = llm.with_structured_output(AssignmentResult)
        user = json.dumps(
            {
                "task": {
                    "title": task.get("title"),
                    "description": (task.get("description") or "")[:600],
                    "priority": task.get("priority"),
                    "tags": task.get("tags") or task.get("required_skills") or [],
                },
                "candidates": [
                    {
                        "user_id": c["id"],
                        "display_name": c.get("display_name", ""),
                        "skills": c.get("skills", []),
                        "workload": c.get("workload", {}),
                    }
                    for c in candidates
                ],
            },
            ensure_ascii=False,
        )
        out = structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        if isinstance(out, AssignmentResult) and out.suggestions:
            out.suggestions.sort(key=lambda s: -s.score)
            out.suggestions = out.suggestions[:3]
            return out
        if isinstance(out, dict):
            r = AssignmentResult(**out)
            if r.suggestions:
                r.suggestions.sort(key=lambda s: -s.score)
                r.suggestions = r.suggestions[:3]
                return r
    except Exception:
        pass
    return fallback
