"""Pydantic schemas for Kanban tasks (US7 / T050)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.diff import DiffReviewStatus
from app.models.task import TaskStatus


class TaskKanbanItem(BaseModel):
    """Task fields returned inside grouped columns (contract GET /tasks)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    priority: int = 0


class TasksGroupedResponse(BaseModel):
    todo: list[TaskKanbanItem] = Field(default_factory=list)
    in_progress: list[TaskKanbanItem] = Field(default_factory=list)
    review: list[TaskKanbanItem] = Field(default_factory=list)
    done: list[TaskKanbanItem] = Field(default_factory=list)
    rejected: list[TaskKanbanItem] = Field(default_factory=list)
    conflict: list[TaskKanbanItem] = Field(default_factory=list)


class TaskMoveRequest(BaseModel):
    """Body for ``POST .../tasks/{task_id}/move`` (US8 / T057)."""

    to: TaskStatus


class TaskMoveResult(BaseModel):
    """JSON returned after a successful move (``plan.md``)."""

    task_id: UUID
    from_status: TaskStatus
    to_status: TaskStatus
    agent_run_id: UUID | None = None


class TaskDiffResponse(BaseModel):
    """Latest diff for ``GET .../tasks/{task_id}/diff`` (US9 / T062, REST contract)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    original_content: str
    modified_content: str
    content: str
    files_affected: list[str]
    review_status: DiffReviewStatus
    created_at: datetime


class TaskApproveResponse(BaseModel):
    """JSON from ``POST .../tasks/{task_id}/approve`` (US9 / T063, REST contract)."""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    status: TaskStatus
    diff_id: UUID
    updated_at: datetime


class TaskRejectRequest(BaseModel):
    """Body for ``POST .../tasks/{task_id}/reject`` (US9 / T064)."""

    feedback: str = Field(..., min_length=1, max_length=10_000)


class TaskRejectResponse(BaseModel):
    """JSON from ``POST .../tasks/{task_id}/reject`` (REST contract)."""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    status: TaskStatus
    feedback_id: UUID
    agent_run_id: UUID
    updated_at: datetime
