"""Pydantic schemas for notifications (US7 / T092)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.notification import Notification


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    content: str
    reference_type: str | None
    reference_id: str | None
    project_id: UUID | None = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_notification(
        cls,
        notification: Notification,
        *,
        project_id: UUID | None = None,
    ) -> NotificationResponse:
        return cls(
            id=notification.id,
            type=str(notification.notification_type),
            content=notification.content,
            reference_type=notification.reference_type,
            reference_id=(
                str(notification.reference_id) if notification.reference_id is not None else None
            ),
            project_id=project_id,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )


class NotificationListResponse(BaseModel):
    total_unread: int
    items: list[NotificationResponse] = Field(default_factory=list)


class MarkReadResponse(BaseModel):
    ok: bool = True


class MarkAllReadResponse(BaseModel):
    marked: int
