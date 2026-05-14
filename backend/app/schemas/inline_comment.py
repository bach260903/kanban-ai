"""Inline comment payloads (US16 / T106)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InlineCommentCreate(BaseModel):
    """``POST /tasks/{task_id}/comments`` body."""

    file_path: str = Field(..., min_length=1, max_length=1000)
    line_number: int = Field(..., ge=1)
    comment_text: str = Field(..., min_length=1, max_length=50_000)


class InlineCommentResponse(BaseModel):
    """One persisted inline comment row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    diff_id: UUID | None
    file_path: str
    line_number: int
    comment_text: str
    created_at: datetime
