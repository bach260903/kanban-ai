"""Pydantic schemas for task dependencies (US4 / T066)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DependencyCreate(BaseModel):
    depends_on_task_id: UUID


class DependencyRef(BaseModel):
    task_id: UUID
    title: str
    status: str


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    depends_on_task_id: UUID
    created_at: datetime


class TaskDependenciesResponse(BaseModel):
    task_id: UUID
    depends_on: list[DependencyRef] = Field(default_factory=list)
    blocked_by: list[DependencyRef] = Field(default_factory=list)


class DependencyGraphNode(BaseModel):
    id: str
    title: str
    status: str


class DependencyGraphResponse(BaseModel):
    nodes: list[DependencyGraphNode] = Field(default_factory=list)
    edges: list[dict[str, str]] = Field(default_factory=list)


class AISuggestResponse(BaseModel):
    added: int
    skipped: int
    total_tasks: int
    graph: DependencyGraphResponse
