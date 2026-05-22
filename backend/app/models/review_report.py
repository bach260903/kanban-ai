"""AI review report and inline comment models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.task import Task


class ReviewStatus(StrEnum):
    """Lifecycle status of an AI review run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class ReviewSuggestion(StrEnum):
    """AI recommendation for the reviewed diff."""

    APPROVE = "approve"
    NEEDS_CHANGES = "needs_changes"


class ReviewSeverity(StrEnum):
    """Severity of a review comment."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReviewReport(Base):
    """Automated code review result for a task."""

    __tablename__ = "review_reports"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_review_reports_score"),
        CheckConstraint(
            "suggestion IN ('approve','needs_changes')",
            name="ck_review_reports_suggestion",
        ),
        CheckConstraint(
            "status IN ('pending','running','complete','error')",
            name="ck_review_reports_status",
        ),
        Index("idx_review_reports_task", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    suggestion: Mapped[ReviewSuggestion | None] = mapped_column(String(20), nullable=True)
    test_runner: Mapped[str | None] = mapped_column(String(50), nullable=True)
    test_pass: Mapped[int | None] = mapped_column(Integer, server_default=text("0"), nullable=True)
    test_fail: Mapped[int | None] = mapped_column(Integer, server_default=text("0"), nullable=True)
    test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship(back_populates="review_reports")
    agent_run: Mapped["AgentRun | None"] = relationship(back_populates="review_reports")
    comments: Mapped[list["ReviewComment"]] = relationship(
        back_populates="review_report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReviewComment(Base):
    """Inline comment on a file within a review report."""

    __tablename__ = "review_comments"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_review_comments_severity",
        ),
        Index("idx_review_comments_report", "review_report_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    review_report_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("review_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[ReviewSeverity] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'info'"),
    )

    review_report: Mapped[ReviewReport] = relationship(back_populates="comments")
