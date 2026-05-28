"""Pydantic schemas for dashboard and project analytics (US6 / T084)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class BackendMetric(BaseModel):
    agent_type: str
    avg_seconds: float = 0.0
    first_approve_rate: float = 0.0
    error_count: int = 0


class MemberMetric(BaseModel):
    display_name: str
    tasks_done: int = 0
    tasks_in_progress: int = 0


class ProjectDashboard(BaseModel):
    id: UUID
    name: str
    primary_language: str
    task_counts: dict[str, int] = Field(default_factory=dict)
    stale_count: int = 0
    member_count: int = 0


class DashboardResponse(BaseModel):
    projects: list[ProjectDashboard] = Field(default_factory=list)


class ErrorBreakdownItem(BaseModel):
    action_type: str
    count: int


class AnalyticsResponse(BaseModel):
    period: str
    by_backend: list[BackendMetric] = Field(default_factory=list)
    by_member: list[MemberMetric] = Field(default_factory=list)
    reviewer_avg_score: float | None = None
    error_breakdown: list[ErrorBreakdownItem] = Field(default_factory=list)


class ActiveTaskItem(BaseModel):
    project_id: str
    project_name: str
    task_id: str
    task_title: str


class AIReviewResponse(BaseModel):
    summary: str
    active_tasks: list[ActiveTaskItem] = Field(default_factory=list)
    generated_at: str
