"""Project membership and invitation request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.project_member import MemberStatus, ProjectRole


class InviteRequest(BaseModel):
    role: ProjectRole
    invitee_email: str | None = None


class InvitationResponse(BaseModel):
    invitation_id: uuid.UUID
    invite_url: str
    expires_at: datetime


class AcceptResponse(BaseModel):
    project_id: uuid.UUID
    role: ProjectRole
    status: MemberStatus = MemberStatus.ACTIVE
    """``pending`` when the generic invite link requires owner approval."""


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    email: str
    role: ProjectRole
    status: MemberStatus = MemberStatus.ACTIVE
    joined_at: datetime


class PendingMemberResponse(BaseModel):
    """Summary of a membership request awaiting owner approval."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    email: str
    role: ProjectRole
    joined_at: datetime


class RoleChangeRequest(BaseModel):
    role: ProjectRole
