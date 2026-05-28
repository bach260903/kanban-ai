"""Project membership and role model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class ProjectRole(StrEnum):
    """Role of a user within a project."""

    OWNER = "owner"
    LEADER = "leader"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class MemberStatus(StrEnum):
    """Lifecycle status of a project membership."""

    ACTIVE = "active"
    PENDING = "pending"


class ProjectMember(Base):
    """Links a user to a project with a specific role."""

    __tablename__ = "project_members"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','leader','developer','viewer')",
            name="ck_project_members_role",
        ),
        CheckConstraint(
            "status IN ('active','pending')",
            name="ck_project_members_status",
        ),
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        Index("idx_project_members_project", "project_id"),
        Index("idx_project_members_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[ProjectRole] = mapped_column(String(20), nullable=False)
    status: Mapped[MemberStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default="active",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")
