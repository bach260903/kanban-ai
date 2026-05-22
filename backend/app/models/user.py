"""User account model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.github_config import GitHubConfig
from app.models.invitation import Invitation
from app.models.notification import Notification
from app.models.project_member import ProjectMember
from app.models.task_template import TaskTemplate
from app.models.webhook import WebhookConfig

if TYPE_CHECKING:
    from app.models.task import Task


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_tasks: Mapped[list["Task"]] = relationship(
        back_populates="assignee",
        foreign_keys="Task.assigned_to",
    )
    memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    invitations_created: Mapped[list[Invitation]] = relationship(
        foreign_keys=[Invitation.created_by],
        back_populates="creator",
        lazy="selectin",
    )
    invitations_accepted: Mapped[list[Invitation]] = relationship(
        foreign_keys=[Invitation.used_by],
        back_populates="accepter",
        lazy="selectin",
    )
    task_templates_created: Mapped[list[TaskTemplate]] = relationship(
        foreign_keys=[TaskTemplate.created_by],
        back_populates="creator",
        lazy="selectin",
    )
    webhook_configs_created: Mapped[list[WebhookConfig]] = relationship(
        foreign_keys=[WebhookConfig.created_by],
        back_populates="creator",
        lazy="selectin",
    )
    github_configs_created: Mapped[list[GitHubConfig]] = relationship(
        foreign_keys=[GitHubConfig.created_by],
        back_populates="creator",
        lazy="selectin",
    )
