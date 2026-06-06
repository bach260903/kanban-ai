"""GitHub integration API (US7 / T102)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_any_member, require_owner
from app.exceptions import NotFoundError
from app.models.github_config import GitHubConfig
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.github import GitHubConfigResponse, GitHubConfigUpsert
from app.services import github_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["github"])


async def _backfill_existing_work(config: GitHubConfig, project_id: uuid.UUID) -> None:
    """Push all work done BEFORE GitHub was linked, so it isn't left only on local.

    Non-fatal: any failure is logged but never blocks linking. Skips silently when
    the project sandbox has no git repo yet (no completed tasks → nothing to push).
    """
    try:
        sandbox = (Path(settings.sandbox_root).expanduser().resolve() / str(project_id)).resolve()
        if not (sandbox / ".git").exists():
            logger.info("github backfill: no local repo for project %s — nothing to push", project_id)
            return
        pushed = await github_service.push_integration_branch(config, sandbox)
        logger.info("github backfill: pushed existing work for project %s (pushed=%s)", project_id, pushed)
    except Exception:
        logger.warning("github backfill: failed to push existing work for project %s", project_id, exc_info=True)


@router.get("/projects/{project_id}/github", response_model=GitHubConfigResponse)
async def get_github_config(
    project_id: uuid.UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GitHubConfigResponse:
    config = await session.scalar(
        select(GitHubConfig).where(GitHubConfig.project_id == project_id)
    )
    if config is None:
        raise NotFoundError("GitHub integration not configured.")
    return GitHubConfigResponse(
        repo_full_name=config.repo_full_name,
        default_base_branch=config.default_base_branch,
        enabled=config.enabled,
    )


@router.put("/projects/{project_id}/github", response_model=GitHubConfigResponse)
async def upsert_github_config(
    project_id: uuid.UUID,
    body: GitHubConfigUpsert,
    current_user: Annotated[User, Depends(get_current_user)],
    _owner: Annotated[ProjectMember, require_owner],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GitHubConfigResponse:
    if not await github_service.validate_config(body.repo_full_name, body.pat):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid PAT or repository not found.",
        )

    encrypted = github_service.encrypt_pat(body.pat)
    config = await session.scalar(
        select(GitHubConfig).where(GitHubConfig.project_id == project_id)
    )
    if config is None:
        config = GitHubConfig(
            project_id=project_id,
            repo_full_name=body.repo_full_name.strip(),
            pat_encrypted=encrypted,
            default_base_branch=body.default_base_branch.strip(),
            enabled=True,
            created_by=current_user.id,
        )
        session.add(config)
    else:
        config.repo_full_name = body.repo_full_name.strip()
        config.pat_encrypted = encrypted
        config.default_base_branch = body.default_base_branch.strip()
        config.enabled = True
        config.created_by = current_user.id

    await session.commit()
    await session.refresh(config)

    # Auto-push toàn bộ work đã làm trước khi gắn GitHub (non-fatal, non-blocking).
    await _backfill_existing_work(config, project_id)

    return GitHubConfigResponse(
        repo_full_name=config.repo_full_name,
        default_base_branch=config.default_base_branch,
        enabled=config.enabled,
    )
