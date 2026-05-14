"""Pydantic schemas for agent runs (US4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.agent_run import AgentRunStatus, AgentType


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID | None
    project_id: UUID
    agent_type: AgentType
    agent_version: str
    status: AgentRunStatus
    input_artifacts: list[str]
    output_artifacts: list[str]
    started_at: datetime
    completed_at: datetime | None
    result: dict[str, Any] | None = None
