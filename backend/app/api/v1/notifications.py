"""Notifications API (US7 / T093)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.task import Task
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    NotificationResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _project_ids_for_task_refs(
    session: AsyncSession,
    items: list[Notification],
) -> dict[UUID, UUID]:
    task_ids = [
        item.reference_id
        for item in items
        if item.reference_type == "task" and item.reference_id is not None
    ]
    if not task_ids:
        return {}
    rows = (
        await session.execute(
            select(Task.id, Task.project_id).where(Task.id.in_(task_ids))
        )
    ).all()
    return {row.id: row.project_id for row in rows}


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    unread_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    total_unread, items = await notification_service.get_notifications(
        session,
        current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    project_by_task = await _project_ids_for_task_refs(session, items)
    return NotificationListResponse(
        total_unread=total_unread,
        items=[
            NotificationResponse.from_notification(
                item,
                project_id=project_by_task.get(item.reference_id),
            )
            for item in items
        ],
    )


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarkReadResponse:
    await notification_service.mark_read(session, notification_id, current_user.id)
    await session.commit()
    return MarkReadResponse()


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MarkAllReadResponse:
    marked = await notification_service.mark_all_read(session, current_user.id)
    await session.commit()
    return MarkAllReadResponse(marked=marked)
