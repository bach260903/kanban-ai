"""Shared LangGraph state payload for agent workflows (US4)."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID


class AgentState(TypedDict):
    project_id: UUID
    task_id: UUID | None
    agent_run_id: UUID
    phase: str
    constitution: str
    intent: str
    spec_content: str
    plan_content: str
    tasks_list: list[str]
    diff_content: str
    feedback: str
    error: str
    coding_backend: str
    # CI gate fields
    ci_run_id: UUID | None      # ID of the triggered PipelineRun
    ci_passed: bool | None      # True=pass, False=fail, None=not run yet
    ci_retry_count: int         # how many times coder was sent back for CI failure
    ci_failure_report: str      # summary of CI failures shown to coder / human
