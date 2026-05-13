"""Pydantic schemas for Kanban tasks (US7 / T050)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
