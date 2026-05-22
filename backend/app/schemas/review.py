"""Pydantic response schemas for AI review reports and comments (US1 / T032)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.review_report import ReviewSeverity, ReviewStatus, ReviewSuggestion


class ReviewCommentResponse(BaseModel):
    """Single inline comment within a review report."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str
    line_number: int | None
    content: str
    severity: ReviewSeverity


class ReviewReportResponse(BaseModel):
    """Full AI review result for a task diff."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    status: ReviewStatus
    score: int | None
    suggestion: ReviewSuggestion | None
    test_runner: str | None
    test_pass: int | None
    test_fail: int | None
    comments: list[ReviewCommentResponse] = []
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
