"""GitHub integration configuration per project."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class GitHubConfig(Base):
    """Encrypted GitHub PAT and repo settings for a project."""

    __tablename__ = "github_configs"
    __table_args__ = (UniqueConstraint("project_id", name="uq_github_configs_project"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    repo_full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pat_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    default_base_branch: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        server_default=text("'main'"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="github_config")
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by],
        back_populates="github_configs_created",
    )
