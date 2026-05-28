"""Webhook configuration and delivery models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class WebhookDeliveryStatus(StrEnum):
    """Delivery attempt lifecycle status."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookConfig(Base):
    """Outbound webhook endpoint registered for a project."""

    __tablename__ = "webhook_configs"

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
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str | None] = mapped_column(String(100), nullable=True)
    events: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="webhook_configs")
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by],
        back_populates="webhook_configs_created",
    )
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        back_populates="webhook_config",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class WebhookDelivery(Base):
    """Single webhook HTTP delivery attempt."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','success','failed','retrying')",
            name="ck_webhook_deliveries_status",
        ),
        Index("idx_webhook_deliveries_config", "webhook_config_id"),
        Index(
            "idx_webhook_deliveries_status",
            "status",
            postgresql_where=text("status IN ('pending','retrying')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    webhook_config_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    webhook_config: Mapped[WebhookConfig] = relationship(back_populates="deliveries")
