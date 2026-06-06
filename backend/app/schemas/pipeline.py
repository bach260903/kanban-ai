"""Pydantic schemas for pipeline & deployment API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Failure analysis schema (defined first — referenced by PipelineStepOut) ───

class FailureAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_id: UUID
    run_id: UUID
    root_cause: str
    confidence: float
    fix_strategy: str
    risk_level: str
    is_auto_fixable: bool
    human_approval_required: bool
    patch_applied: bool
    patch_summary: str | None
    retry_triggered: bool
    retry_attempt: int
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


# ── Pipeline step / run ────────────────────────────────────────────────────────

class PipelineStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    step_key: str
    status: str
    attempt: int
    logs: str | None
    ai_reasoning: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    created_at: datetime
    failure_analyses: list[FailureAnalysisOut] = []


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    task_id: UUID | None
    task_title: str | None = None
    status: str
    triggered_by: str | None
    branch_name: str | None
    commit_sha: str | None
    ai_summary: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    steps: list[PipelineStepOut] = []


# ── Deployment ─────────────────────────────────────────────────────────────────

class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    task_id: UUID | None
    run_id: UUID | None
    status: str
    environment: str
    provider: str | None
    external_id: str | None
    preview_url: str | None
    branch_name: str | None
    commit_sha: str | None
    deploy_logs: str | None
    error_message: str | None
    risk_score: float | None
    duration_ms: int | None
    deployed_at: datetime | None
    created_at: datetime


# ── Deployment config schemas ──────────────────────────────────────────────────

class DeploymentConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    provider: str
    project_name: str
    team_id: str | None
    base_url: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class DeploymentConfigCreate(BaseModel):
    provider: str = Field(..., pattern="^(vercel|railway|none)$")
    token: str = Field(..., min_length=1)
    project_name: str = Field(..., min_length=1)
    team_id: str | None = None
    base_url: str | None = None
    enabled: bool = True


class DeploymentConfigTestRequest(BaseModel):
    provider: str = Field(..., pattern="^(vercel|railway)$")
    token: str = Field(..., min_length=1)
    project_name: str = Field(..., min_length=1)
    team_id: str | None = None


class DeploymentConfigTestResponse(BaseModel):
    ok: bool
    message: str
