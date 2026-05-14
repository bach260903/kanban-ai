"""API schemas for project memory entries (US13 / T095)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryEntryResponse(BaseModel):
    """Single ``memory_entries`` row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    task_id: UUID | None
    entry_timestamp: datetime
    summary: str
    files_affected: list[str]
    lessons_learned: str
    created_at: datetime
    updated_at: datetime


class MemoryEntryUpdate(BaseModel):
    """Partial update for PO edits (at least one field required)."""

    summary: str | None = Field(default=None, max_length=20_000)
    lessons_learned: str | None = Field(default=None, max_length=50_000)

    @model_validator(mode="after")
    def validate_patch(self) -> MemoryEntryUpdate:
        if self.summary is None and self.lessons_learned is None:
            raise ValueError("Provide at least one of summary or lessons_learned.")
        if self.summary is not None and not self.summary.strip():
            raise ValueError("summary cannot be blank when provided.")
        if self.lessons_learned is not None and not self.lessons_learned.strip():
            raise ValueError("lessons_learned cannot be blank when provided.")
        return self
