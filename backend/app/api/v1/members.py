"""Project members and invitation endpoints."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    require_any_member,
    require_leader_or_above,
    require_owner,
)
from app.models.invitation import Invitation, InviteRole
from app.models.project_member import ProjectMember, ProjectRole
from app.models.user import User
from app.schemas.member import (
    AcceptResponse,
    InvitationResponse,
    InviteRequest,
    MemberResponse,
    RoleChangeRequest,
)

router = APIRouter(tags=["members"])

_INVITE_ROLES = {ProjectRole.LEADER, ProjectRole.DEVELOPER, ProjectRole.VIEWER}


def _project_role(value: ProjectRole | InviteRole | str) -> ProjectRole:
    raw = value.value if isinstance(value, (ProjectRole, InviteRole)) else value
    return ProjectRole(raw)


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(
    project_id: uuid.UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MemberResponse]:
    rows = await session.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    return [
        MemberResponse(
            user_id=pm.user_id,
            display_name=user.display_name,
            email=user.email,
            role=pm.role,
            joined_at=pm.joined_at,
        )
        for pm, user in rows.all()
    ]


@router.post(
    "/projects/{project_id}/members/invite",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    project_id: uuid.UUID,
    body: InviteRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    _owner: Annotated[ProjectMember, require_owner],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationResponse:
    if body.role not in _INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite with owner role",
        )
    token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    invitation = Invitation(
        project_id=project_id,
        invitee_email=body.invitee_email,
        role=InviteRole(body.role.value),
        token=token,
        created_by=current_user.id,
        expires_at=expires_at,
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    base = str(request.base_url).rstrip("/")
    invite_url = f"{base}/invitations/{token}"
    return InvitationResponse(
        invitation_id=invitation.id,
        invite_url=invite_url,
        expires_at=invitation.expires_at,
    )


@router.get("/invitations/{token}")
async def get_invitation(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    invitation = await session.scalar(
        select(Invitation).where(Invitation.token == token)
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    return {
        "invitation_id": invitation.id,
        "project_id": invitation.project_id,
        "role": _project_role(invitation.role),
        "invitee_email": invitation.invitee_email,
        "is_expired": invitation.is_expired,
        "is_used": invitation.is_used,
    }


@router.post("/invitations/{token}/accept", response_model=AcceptResponse)
async def accept_invitation(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AcceptResponse:
    invitation = await session.scalar(
        select(Invitation).where(Invitation.token == token)
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    if invitation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation expired",
        )
    if invitation.is_used:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Invitation already used",
        )
    existing = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == invitation.project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already a member",
        )
    member_role = _project_role(invitation.role)
    session.add(
        ProjectMember(
            project_id=invitation.project_id,
            user_id=current_user.id,
            role=member_role,
        )
    )
    invitation.used_at = datetime.now(timezone.utc)
    invitation.used_by = current_user.id
    await session.commit()
    return AcceptResponse(project_id=invitation.project_id, role=member_role)


@router.patch(
    "/projects/{project_id}/members/{user_id}",
    response_model=MemberResponse,
)
async def change_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: RoleChangeRequest,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MemberResponse:
    row = await session.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    member, user = result
    if body.role == ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign owner role",
        )
    if _project_role(member.role) == ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change project owner role",
        )
    member.role = body.role
    await session.commit()
    await session.refresh(member)
    return MemberResponse(
        user_id=member.user_id,
        display_name=user.display_name,
        email=user.email,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete(
    "/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    _owner: Annotated[ProjectMember, require_owner],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    if _project_role(member.role) == ProjectRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove project owner",
        )
    await session.delete(member)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
