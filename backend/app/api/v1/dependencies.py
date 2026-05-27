"""Task dependency API (US4 / T067)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_any_member, require_developer_or_above
from app.models.project_member import ProjectMember
from app.schemas.dependency import (
    DependencyCreate,
    DependencyGraphResponse,
    DependencyRef,
    DependencyResponse,
    TaskDependenciesResponse,
)
from app.services import dependency_service
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["dependencies"])


@router.get(
    "/{project_id}/tasks/{task_id}/dependencies",
    response_model=TaskDependenciesResponse,
)
async def get_task_dependencies(
    project_id: UUID,
    task_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskDependenciesResponse:
    await ProjectService.get(session, project_id)
    data = await dependency_service.list_task_dependencies(session, task_id, project_id)
    return TaskDependenciesResponse(
        task_id=UUID(str(data["task_id"])),
        depends_on=[DependencyRef.model_validate(row) for row in data["depends_on"]],
        blocked_by=[DependencyRef.model_validate(row) for row in data["blocked_by"]],
    )


@router.post(
    "/{project_id}/tasks/{task_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task_dependency(
    project_id: UUID,
    task_id: UUID,
    body: DependencyCreate,
    _developer: Annotated[ProjectMember, require_developer_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DependencyResponse:
    await ProjectService.get(session, project_id)
    row, created = await dependency_service.add_dependency(
        session,
        task_id,
        body.depends_on_task_id,
        project_id,
    )
    await session.commit()
    await session.refresh(row)
    payload = DependencyResponse.model_validate(row)
    if created:
        return payload
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json"),
    )


@router.delete(
    "/{project_id}/tasks/{task_id}/dependencies/{dep_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_task_dependency(
    project_id: UUID,
    task_id: UUID,
    dep_id: UUID,
    _developer: Annotated[ProjectMember, require_developer_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await ProjectService.get(session, project_id)
    await dependency_service.remove_dependency(
        session,
        task_id,
        dep_id,
        project_id=project_id,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{project_id}/dependency-graph",
    response_model=DependencyGraphResponse,
)
async def get_dependency_graph(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DependencyGraphResponse:
    await ProjectService.get(session, project_id)
    graph = await dependency_service.get_dependency_graph(session, project_id)
    return DependencyGraphResponse.model_validate(graph)
