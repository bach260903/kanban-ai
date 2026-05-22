"""Project invitation model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class InviteRole(StrEnum):
    """Role granted when an invitation is accepted."""

    LEADER = "leader"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Invitation(Base):
    """Invite link or email-targeted invitation to join a project."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('leader','developer','viewer')",
            name="ck_invitations_role",
        ),
        UniqueConstraint("token", name="uq_invitations_token"),
        Index("idx_invitations_token", "token"),
        Index("idx_invitations_project", "project_id"),
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
    invitee_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[InviteRole] = mapped_column(String(20), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    project: Mapped["Project"] = relationship(back_populates="invitations")
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="invitations_created",
    )
    accepter: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[used_by],
        back_populates="invitations_accepted",
    )

    @property
    def is_expired(self) -> bool:
        """Return True if the invitation has passed its expiry time."""
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires

    @property
    def is_used(self) -> bool:
        """Return True if the invitation has already been accepted."""
        return self.used_at is not None
