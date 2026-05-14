"""Codebase map read + refresh (US14 / T099)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.exceptions import SandboxEscapeError
from app.middleware.auth import require_jwt
from app.models.codebase_map import CodebaseMap
from app.services.codebase_mapper import CodebaseMapperService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["codebase"])

_SCAN_LANGS = frozenset({"python", "javascript", "typescript"})


def _sandbox_project_root(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


async def _latest_map(session: AsyncSession, project_id: UUID) -> CodebaseMap | None:
    stmt = (
        select(CodebaseMap)
        .where(CodebaseMap.project_id == project_id)
        .order_by(CodebaseMap.generated_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


@router.get("/{project_id}/codebase-map")
async def get_codebase_map(
    project_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
    refresh: bool = Query(False, description="When true, re-scan sandbox and store a new map."),
) -> dict[str, Any]:
    """Return latest cached map, or run a synchronous tree-sitter scan when missing or ``refresh``."""
    project = await ProjectService.get(session, project_id)
    lang = (project.primary_language or "python").lower()
    if lang not in _SCAN_LANGS:
        lang = "python"

    if not refresh:
        row = await _latest_map(session, project_id)
        if row is not None and isinstance(row.map_json, dict):
            return row.map_json

    root = _sandbox_project_root(project_id)
    if not root.is_dir():
        root.mkdir(parents=True, exist_ok=True)

    try:
        payload = await CodebaseMapperService.scan_and_store(
            session,
            project_id=project_id,
            project_root=root,
            language=lang,
            task_id=None,
        )
    except Exception:
        logger.exception("codebase map scan failed project_id=%s", project_id)
        raise
    await session.commit()
    return payload
