"""Pydantic schemas for projects."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import CodingBackend, ProjectStatus

PrimaryLanguage = Literal["python", "javascript", "typescript"]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    primary_language: PrimaryLanguage
    coding_backend: CodingBackend = CodingBackend.groq


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    coding_backend: CodingBackend | None = None


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
    coding_backend: CodingBackend
    updated_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    primary_language: str
    constitution: str
    status: ProjectStatus
    coding_backend: CodingBackend
    created_at: datetime
    updated_at: datetime
