"""Pipeline run ORM model — CI/CD orchestration layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_step import PipelineStep
    from app.models.deployment import Deployment


class PipelineRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','success','failure','cancelled')",
            name="ck_pipeline_runs_status",
        ),
        Index("idx_pipeline_runs_project", "project_id"),
        Index("idx_pipeline_runs_task", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'queued'"),
    )
    triggered_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="'task_approved' | 'manual' | 'push'",
    )
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    steps: Mapped[list["PipelineStep"]] = relationship(
        "PipelineStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="PipelineStep.created_at",
        lazy="selectin",
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
