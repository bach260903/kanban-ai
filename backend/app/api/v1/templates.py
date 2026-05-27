"""Task template API (US5 / T077)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.template import TemplateCreate, TemplateResponse
from app.services import template_service
from app.services.project_service import ProjectService

router = APIRouter(prefix="/templates", tags=["templates"])


async def _ensure_project_access(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> None:
    await ProjectService.get(session, project_id)
    await template_service.require_project_member(session, project_id, user_id)


@router.get("", response_model=list[TemplateResponse])
async def list_task_templates(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    project_id: Annotated[UUID | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
) -> list[TemplateResponse]:
    if scope not in (None, "global", "project"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope must be 'global', 'project', or omitted.",
        )
    if scope in (None, "project") and project_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id is required when scope is omitted or 'project'.",
        )
    if project_id is not None:
        await _ensure_project_access(session, project_id, current_user.id)
    rows = await template_service.list_templates(
        session,
        project_id=project_id,
        scope=scope,
    )
    return [TemplateResponse.model_validate(row) for row in rows]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_task_template(
    body: TemplateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateResponse:
    if body.scope == "project" and body.project_id is not None:
        await ProjectService.get(session, body.project_id)
    row = await template_service.create_template(session, body, current_user.id)
    await session.commit()
    await session.refresh(row)
    return TemplateResponse.model_validate(row)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_template(
    template_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await template_service.delete_template(session, template_id, current_user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
