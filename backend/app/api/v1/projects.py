"""Projects CRUD (US1) — contract: ``/api/v1/projects``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_jwt
from app.schemas.intent import IntentResponse
from app.schemas.project import (
    ConstitutionResponse,
    ConstitutionUpdate,
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.intent_service import IntentService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectListItem])
async def list_projects(
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectListItem]:
    projects = await ProjectService.list(session)
    return [ProjectListItem.model_validate(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    project = await ProjectService.create(session, data)
    await session.commit()
    await session.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    project = await ProjectService.get(session, project_id)
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    project = await ProjectService.update(session, project_id, data)
    await session.commit()
    await session.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_project(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await ProjectService.archive(session, project_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/constitution", response_model=ConstitutionResponse)
async def get_constitution(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConstitutionResponse:
    project = await ProjectService.get_constitution(session, project_id)
    return ConstitutionResponse(
        project_id=project.id,
        content=project.constitution,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}/intents", response_model=list[IntentResponse])
async def list_intents(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[IntentResponse]:
    await ProjectService.get(session, project_id)
    intents = await IntentService.list_by_project(session, project_id)
    return [IntentResponse.model_validate(i) for i in intents]


@router.put("/{project_id}/constitution", response_model=ConstitutionResponse)
async def update_constitution(
    project_id: UUID,
    data: ConstitutionUpdate,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConstitutionResponse:
    project = await ProjectService.update_constitution(session, project_id, data.content)
    await session.commit()
    await session.refresh(project)
    return ConstitutionResponse(
        project_id=project.id,
        content=project.constitution,
        updated_at=project.updated_at,
    )
