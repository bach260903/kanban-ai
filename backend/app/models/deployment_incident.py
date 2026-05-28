"""Deployment incident — anomaly / degradation event — Phase 4."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IncidentType(StrEnum):
    HEALTH_FAIL = "health_fail"
    LATENCY_SPIKE = "latency_spike"
    ERROR_SPIKE = "error_spike"
    CRASH = "crash"
    MANUAL = "manual"


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DeploymentIncident(Base):
    """Anomaly detected in a live deployment — may trigger rollback."""

    __tablename__ = "deployment_incidents"
    __table_args__ = (
        Index("idx_incident_deployment", "deployment_id"),
        Index("idx_incident_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    deployment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'medium'")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON snapshot: {http_status, latency_ms, consecutive_failures, ...}
    metric_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="JSON metrics at time of incident"
    )
    rollback_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
