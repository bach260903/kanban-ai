"""In-app notification model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class NotificationType(StrEnum):
    """Supported notification event types."""

    TASK_ASSIGNED = "task_assigned"
    TASK_NEEDS_REVIEW = "task_needs_review"
    TASK_DONE = "task_done"
    TASK_UNBLOCKED = "task_unblocked"
    AGENT_ERROR = "agent_error"
    INVITE_ACCEPTED = "invite_accepted"
    REVIEW_COMPLETE = "review_complete"
    JOIN_REQUESTED = "join_requested"


class Notification(Base):
    """User notification with optional polymorphic reference."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "idx_notifications_user_unread",
            "user_id",
            "is_read",
            postgresql_where=text("is_read = false"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        "type",
        String(50),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
