"""Rollback event — records every automated or manual rollback — Phase 4."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RollbackStatus(StrEnum):
    PENDING = "pending"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RollbackTrigger(StrEnum):
    AI_ANOMALY = "ai_anomaly"
    HEALTH_FAIL = "health_fail"
    MANUAL = "manual"


class RollbackEvent(Base):
    """Records a rollback action for observability and audit trail."""

    __tablename__ = "rollback_events"
    __table_args__ = (
        Index("idx_rollback_deployment", "deployment_id"),
        Index("idx_rollback_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        comment="The failed deployment being rolled back",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_by: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'manual'"),
    )
    previous_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
        comment="The healthy deployment we're rolling back to",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'"),
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    alert_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
