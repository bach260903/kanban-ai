"""Read-only audit log listing (T071)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_jwt
from app.schemas.audit import AuditLogListItem, AuditLogsPageResponse
from app.services.audit_service import list_audit_logs_for_project
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["audit-logs"])

_MAX_PAGE = 100


@router.get("/{project_id}/audit-logs", response_model=AuditLogsPageResponse)
async def list_project_audit_logs(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE)] = 50,
) -> AuditLogsPageResponse:
    await ProjectService.get(session, project_id)
    rows, total = await list_audit_logs_for_project(session, project_id, offset=offset, limit=limit)
    return AuditLogsPageResponse(
        items=[AuditLogListItem.model_validate(r) for r in rows],
        total=total,
        offset=offset,
        limit=limit,
    )
