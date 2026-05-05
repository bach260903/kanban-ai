"""Shared LangGraph state for the multi-agent harness.

Phase 2 deliverable. Phase 3 will fill in nodes/tools that mutate this state.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

Intent = Literal["plan", "assign", "monitor", "report", "execute", "end"]


class AlertItem(TypedDict, total=False):
    severity: Literal["info", "warn", "critical"]
    evidence: str
    suggestion: str


class TaskDraft(TypedDict, total=False):
    title: str
    description: str
    est_hours: float
    required_skills: list[str]
    depends_on: list[str]


class AssignmentDecision(TypedDict, total=False):
    task_id: str
    user_id: str
    score: float
    reason: str


class ToolCallRecord(TypedDict, total=False):
    tool: str
    args: dict[str, Any]
    result: Any
    started_at: str
    finished_at: str
    error: Optional[str]


class AgentState(TypedDict, total=False):
    user_message: str
    board_id: str
    user_id: str

    messages: Annotated[list[BaseMessage], add_messages]

    intent: Intent
    iter_count: int

    plan: list[TaskDraft]
    assignments: list[AssignmentDecision]
    alerts: list[AlertItem]
    report_md: Optional[str]

    tool_calls: list[ToolCallRecord]
    error: Optional[str]


MAX_ITERS: int = 6
MAX_TOOL_CALLS_PER_NODE: int = 5
