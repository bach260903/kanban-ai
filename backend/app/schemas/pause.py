"""REST schemas for task pause / resume (US11 / T085)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskResumeBody(BaseModel):
    """Optional body for ``POST .../tasks/{task_id}/resume``."""

    steering_instructions: str | None = Field(default=None, max_length=10_000)


class PauseResumeResponse(BaseModel):
    """JSON after pause or resume; ``paused`` reflects Redis after the operation."""

    task_id: UUID
    paused: bool


class PauseStateResponse(BaseModel):
    """Combined Redis pause flag and persisted ``agent_pause_states`` row (if any)."""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    is_paused: bool
    state: str | None = None
    steering_instructions: str | None = None
    agent_run_id: UUID | None = None
    paused_at: datetime | None = None
    resumed_at: datetime | None = None
