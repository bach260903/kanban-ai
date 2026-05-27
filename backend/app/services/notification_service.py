"""In-app notification helpers and queries (US7 / T090–T091)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.notification import Notification, NotificationType
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task

_LEADER_ROLES = (ProjectRole.OWNER, ProjectRole.LEADER)


async def create_notification(
    session: AsyncSession,
    user_id: UUID,
    notification_type: NotificationType,
    content: str,
    reference_type: str | None = None,
    reference_id: str | UUID | None = None,
) -> Notification:
    ref_uuid: UUID | None = None
    if reference_id is not None:
        ref_uuid = reference_id if isinstance(reference_id, UUID) else UUID(str(reference_id))
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        content=content,
        reference_type=reference_type,
        reference_id=ref_uuid,
    )
    session.add(notification)
    await session.flush()
    return notification


async def notify_task_assigned(
    session: AsyncSession,
    task: Task,
    assigned_to_user_id: UUID,
) -> None:
    await create_notification(
        session,
        assigned_to_user_id,
        NotificationType.TASK_ASSIGNED,
        f"Bạn được giao task: {task.title}",
        reference_type="task",
        reference_id=task.id,
    )


async def _notify_project_leaders(
    session: AsyncSession,
    task: Task,
    notification_type: NotificationType,
    content: str,
) -> None:
    members = (
        await session.scalars(
            select(ProjectMember).where(
                ProjectMember.project_id == task.project_id,
                ProjectMember.role.in_(_LEADER_ROLES),
            )
        )
    ).all()
    for member in members:
        await create_notification(
            session,
            member.user_id,
            notification_type,
            content,
            reference_type="task",
            reference_id=task.id,
        )


async def notify_task_needs_review(session: AsyncSession, task: Task) -> None:
    await _notify_project_leaders(
        session,
        task,
        NotificationType.TASK_NEEDS_REVIEW,
        f"Task cần review: {task.title}",
    )


async def notify_agent_error(session: AsyncSession, task: Task) -> None:
    await _notify_project_leaders(
        session,
        task,
        NotificationType.AGENT_ERROR,
        f"Agent lỗi trên task: {task.title}",
    )


async def notify_task_unblocked(
    session: AsyncSession,
    task: Task,
    user_id: UUID,
) -> None:
    await create_notification(
        session,
        user_id,
        NotificationType.TASK_UNBLOCKED,
        f"Task đã được mở khóa: {task.title}",
        reference_type="task",
        reference_id=task.id,
    )


async def get_notifications(
    session: AsyncSession,
    user_id: UUID,
    *,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[Notification]]:
    total_unread = int(
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )
    query = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    items = list((await session.scalars(query)).all())
    return total_unread, items


async def mark_read(
    session: AsyncSession,
    notification_id: UUID,
    user_id: UUID,
) -> Notification:
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if notification is None:
        raise NotFoundError("Notification not found.")
    notification.is_read = True
    await session.flush()
    return notification


async def mark_all_read(session: AsyncSession, user_id: UUID) -> int:
    result = await session.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await session.flush()
    return int(result.rowcount or 0)
