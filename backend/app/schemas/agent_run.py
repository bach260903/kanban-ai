"""Pydantic schemas for agent runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.agent_run import AgentRunStatus, AgentType


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    task_id: UUID | None
    agent_type: AgentType
    status: AgentRunStatus
    input_artifacts: list[str]
    output_artifacts: list[str]
    started_at: datetime
    completed_at: datetime | None
    result: Any | None = None
