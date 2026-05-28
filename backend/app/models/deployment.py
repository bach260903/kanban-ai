"""Deployment ORM model — tracks what was deployed per pipeline run."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_run import PipelineRun


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"


class DeploymentEnvironment(StrEnum):
    PREVIEW = "preview"
    STAGING = "staging"
    PRODUCTION = "production"


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','deploying','healthy','degraded','rolled_back','skipped')",
            name="ck_deployments_status",
        ),
        Index("idx_deployments_project", "project_id"),
        Index("idx_deployments_task", "task_id"),
        Index("idx_deployments_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True,
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'"),
    )
    environment: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'preview'"),
    )
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preview_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deploy_logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phase 4: health monitoring + rollback tracking
    health_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="unknown | healthy | degraded | critical",
    )
    rollback_of_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    run: Mapped["PipelineRun | None"] = relationship("PipelineRun", back_populates="deployments")
