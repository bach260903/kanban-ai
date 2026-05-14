"""Project memory CRUD (US13 / T095)."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_jwt
from app.schemas.memory import MemoryEntryResponse, MemoryEntryUpdate
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["memory"])


@router.get("/{project_id}/memory", response_model=list[MemoryEntryResponse])
async def list_project_memory(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MemoryEntryResponse]:
    await ProjectService.get(session, project_id)
    rows = await MemoryService.list_for_project(session, project_id)
    return [MemoryEntryResponse.model_validate(r) for r in rows]


@router.get("/{project_id}/memory/{entry_id}", response_model=MemoryEntryResponse)
async def get_memory_entry(
    project_id: UUID,
    entry_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryEntryResponse:
    await ProjectService.get(session, project_id)
    row = await MemoryService.get_entry(session, project_id, entry_id)
    return MemoryEntryResponse.model_validate(row)


@router.put("/{project_id}/memory/{entry_id}", response_model=MemoryEntryResponse)
async def update_memory_entry(
    project_id: UUID,
    entry_id: UUID,
    body: MemoryEntryUpdate,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryEntryResponse:
    await ProjectService.get(session, project_id)
    row = await MemoryService.update_entry(
        session,
        project_id,
        entry_id,
        summary=body.summary,
        lessons_learned=body.lessons_learned,
    )
    try:
        await MemoryService.export_memory_file(session, project_id)
    except Exception:
        logger.exception("export_memory_file after memory update failed project_id=%s", project_id)
    await session.commit()
    await session.refresh(row)
    return MemoryEntryResponse.model_validate(row)


@router.delete("/{project_id}/memory/{entry_id}", status_code=204)
async def delete_memory_entry(
    project_id: UUID,
    entry_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await ProjectService.get(session, project_id)
    await MemoryService.delete_entry(session, project_id, entry_id)
    try:
        await MemoryService.export_memory_file(session, project_id)
    except Exception:
        logger.exception("export_memory_file after memory delete failed project_id=%s", project_id)
    await session.commit()
    return Response(status_code=204)
