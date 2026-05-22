"""Project ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.github_config import GitHubConfig
    from app.models.invitation import Invitation
    from app.models.project_member import ProjectMember
    from app.models.task_template import TaskTemplate
    from app.models.webhook import WebhookConfig

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class CodingBackend(StrEnum):
    groq = "groq"
    claude_code = "claude_code"
    openai = "openai"
    gemini = "gemini"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','archived')",
            name="ck_projects_status",
        ),
        CheckConstraint(
            "coding_backend IN ('groq','claude_code','openai','gemini')",
            name="ck_projects_coding_backend",
        ),
        UniqueConstraint("name", name="uq_projects_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_language: Mapped[str] = mapped_column(String(50), nullable=False)
    constitution: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    status: Mapped[ProjectStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
    )
    coding_backend: Mapped[CodingBackend] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'groq'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feedbacks: Mapped[list["Feedback"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="project",
        lazy="selectin",
    )
    intents: Mapped[list["Intent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    task_templates: Mapped[list["TaskTemplate"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    webhook_configs: Mapped[list["WebhookConfig"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    github_config: Mapped["GitHubConfig | None"] = relationship(
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
