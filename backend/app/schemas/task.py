"""Pydantic schemas for Kanban tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus

TaskMoveTo = Literal["in_progress", "review", "done"]


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    created_at: datetime
    updated_at: datetime


class TaskMoveRequest(BaseModel):
    """Body for ``POST .../tasks/{id}/move`` (contracts/rest-api.md)."""

    to: TaskMoveTo


class RejectRequest(BaseModel):
    """Body for ``POST .../tasks/{id}/reject``."""

    feedback: str = Field(..., min_length=1)
