"""GitHub integration API (US7 / T102)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_any_member, require_owner
from app.exceptions import NotFoundError
from app.models.github_config import GitHubConfig
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.github import GitHubConfigResponse, GitHubConfigUpsert
from app.services import github_service

router = APIRouter(tags=["github"])


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
    return GitHubConfigResponse(
        repo_full_name=config.repo_full_name,
        default_base_branch=config.default_base_branch,
        enabled=config.enabled,
    )
