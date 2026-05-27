"""Task template CRUD (US5 / T075)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DuplicateNameError, NotFoundError
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task_template import TaskTemplate, TemplateScope
from app.schemas.template import TemplateCreate

_LEADER_ROLES = (ProjectRole.OWNER, ProjectRole.LEADER)


async def require_project_member(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> None:
    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view templates for this project.",
        )


async def _require_leader_in_project(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> None:
    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role.in_(_LEADER_ROLES),
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage templates.",
        )


async def _require_leader_anywhere(
    session: AsyncSession,
    user_id: UUID,
) -> None:
    member = await session.scalar(
        select(ProjectMember)
        .where(
            ProjectMember.user_id == user_id,
            ProjectMember.role.in_(_LEADER_ROLES),
        )
        .limit(1)
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage global templates.",
        )


async def list_templates(
    session: AsyncSession,
    project_id: UUID | None,
    scope: str | None = None,
) -> list[TaskTemplate]:
    """List templates visible for a project (global + project-scoped)."""
    if scope == "global":
        stmt = select(TaskTemplate).where(TaskTemplate.scope == TemplateScope.GLOBAL)
    elif scope == "project":
        stmt = select(TaskTemplate).where(
            TaskTemplate.project_id == project_id,
            TaskTemplate.scope == TemplateScope.PROJECT,
        )
    else:
        stmt = select(TaskTemplate).where(
            or_(
                TaskTemplate.scope == TemplateScope.GLOBAL,
                TaskTemplate.project_id == project_id,
            )
        )
    stmt = stmt.order_by(TaskTemplate.name)
    result = await session.scalars(stmt)
    return list(result.all())


async def create_template(
    session: AsyncSession,
    data: TemplateCreate,
    created_by: UUID,
) -> TaskTemplate:
    scope = TemplateScope(data.scope)
    if scope == TemplateScope.PROJECT:
        assert data.project_id is not None
        await _require_leader_in_project(session, data.project_id, created_by)
        existing = await session.scalar(
            select(TaskTemplate).where(
                TaskTemplate.project_id == data.project_id,
                TaskTemplate.name == data.name,
            )
        )
    else:
        await _require_leader_anywhere(session, created_by)
        existing = await session.scalar(
            select(TaskTemplate).where(
                TaskTemplate.scope == TemplateScope.GLOBAL,
                TaskTemplate.name == data.name,
            )
        )
    if existing is not None:
        raise DuplicateNameError(f"Template name '{data.name}' already exists.")

    row = TaskTemplate(
        name=data.name,
        title_template=data.title_template,
        description_template=data.description_template or "",
        scope=scope,
        project_id=data.project_id if scope == TemplateScope.PROJECT else None,
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return row


async def _user_can_delete_template(
    session: AsyncSession,
    template: TaskTemplate,
    current_user_id: UUID,
) -> bool:
    if template.created_by == current_user_id:
        return True
    if template.project_id is None:
        leader = await session.scalar(
            select(ProjectMember)
            .where(
                ProjectMember.user_id == current_user_id,
                ProjectMember.role.in_(_LEADER_ROLES),
            )
            .limit(1)
        )
        return leader is not None
    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == template.project_id,
            ProjectMember.user_id == current_user_id,
            ProjectMember.role.in_(_LEADER_ROLES),
        )
    )
    return member is not None


async def delete_template(
    session: AsyncSession,
    template_id: UUID,
    current_user_id: UUID,
) -> None:
    template = await session.get(TaskTemplate, template_id)
    if template is None:
        raise NotFoundError("Template not found.")
    if not await _user_can_delete_template(session, template, current_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete this template.",
        )
    await session.delete(template)
    await session.flush()
