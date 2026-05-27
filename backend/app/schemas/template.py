"""Pydantic schemas for task templates (US5 / T076)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    title_template: str = Field(..., min_length=1, max_length=255)
    description_template: str = ""
    scope: Literal["project", "global"]
    project_id: UUID | None = None

    @field_validator("name", "title_template", mode="before")
    @classmethod
    def strip_required_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_scope_and_project(self) -> TemplateCreate:
        if self.scope == "project" and self.project_id is None:
            raise ValueError("project_id is required for project-scoped templates.")
        if self.scope == "global":
            self.project_id = None
        return self


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    title_template: str
    description_template: str
    scope: str
    project_id: UUID | None
    created_by: UUID | None
    created_at: datetime
