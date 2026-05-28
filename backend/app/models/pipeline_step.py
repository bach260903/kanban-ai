"""Pipeline step ORM model — individual CI/CD step execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_run import PipelineRun
    from app.models.step_failure_analysis import StepFailureAnalysis


class PipelineStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','success','failure','skipped')",
            name="ck_pipeline_steps_status",
        ),
        Index("idx_pipeline_steps_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="'test' | 'lint' | 'build'",
    )
    status: Mapped[PipelineStepStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="steps")
    failure_analyses: Mapped[list["StepFailureAnalysis"]] = relationship(
        "StepFailureAnalysis",
        back_populates="step",
        cascade="all, delete-orphan",
        order_by="StepFailureAnalysis.created_at",
        lazy="selectin",
    )
