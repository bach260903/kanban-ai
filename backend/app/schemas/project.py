"""Pydantic schemas for projects."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus

PrimaryLanguage = Literal["python", "javascript", "typescript"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    primary_language: PrimaryLanguage


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class ConstitutionUpdate(BaseModel):
    content: str = ""


class ConstitutionResponse(BaseModel):
    project_id: UUID
    content: str
    updated_at: datetime | None = None


class ProjectListItem(BaseModel):
    """Subset returned by ``GET /api/v1/projects`` (contract)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    primary_language: str
    status: ProjectStatus
    updated_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    primary_language: str
    constitution: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
