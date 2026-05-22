"""Reusable task template model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class TemplateScope(StrEnum):
    """Whether a template is project-scoped or global."""

    PROJECT = "project"
    GLOBAL = "global"


class TaskTemplate(Base):
    """Named template for pre-filling task title and description."""

    __tablename__ = "task_templates"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('project','global')",
            name="ck_task_templates_scope",
        ),
        UniqueConstraint("project_id", "name", name="uq_task_templates_project_name"),
        Index(
            "uq_task_templates_global_name",
            "name",
            unique=True,
            postgresql_where=text("project_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title_template: Mapped[str] = mapped_column(String(255), nullable=False)
    description_template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    scope: Mapped[TemplateScope] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'project'"),
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
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

    project: Mapped["Project | None"] = relationship(back_populates="task_templates")
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by],
        back_populates="task_templates_created",
    )
