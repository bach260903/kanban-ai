"""Deployment provider configuration per project (Vercel / Railway)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class DeployProvider(StrEnum):
    VERCEL = "vercel"
    RAILWAY = "railway"
    NONE = "none"


class DeploymentConfig(Base):
    """Stores encrypted provider tokens + project identifiers for auto-deployment."""

    __tablename__ = "deployment_configs"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('vercel','railway','none')",
            name="ck_deployment_configs_provider",
        ),
        UniqueConstraint("project_id", name="uq_deployment_configs_project"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    provider: Mapped[DeployProvider] = mapped_column(String(20), nullable=False)
    token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    project_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Provider-side project name (Vercel projectId or Railway serviceId)",
    )
    team_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Vercel team ID / Railway team slug (optional)",
    )
    base_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Custom preview base URL pattern (optional)",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"),
    )
    # Phase 4: alert webhooks + health monitoring config
    discord_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    slack_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_check_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, server_default=text("'/health'"),
    )
    alert_on_anomaly: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"),
    )
    monitor_duration_minutes: Mapped[int] = mapped_column(
        nullable=False, server_default=text("5"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    project: Mapped["Project"] = relationship("Project")
