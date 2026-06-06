"""Task ORM model (Kanban + WIP partial unique index)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.project import Project
from app.models.task_dependency import TaskDependency

if TYPE_CHECKING:
    from app.models.review_report import ReviewReport
    from app.models.user import User


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo','in_progress','review','done')",
            name="ck_tasks_status",
        ),
        Index("idx_tasks_project_status", "project_id", "status"),
        Index(
            "one_in_progress_per_assignee",
            "project_id",
            "assigned_to",
            unique=True,
            postgresql_where=text("status = 'in_progress' AND assigned_to IS NOT NULL"),
        ),
        Index("idx_tasks_assigned_to", "assigned_to"),
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
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'todo'"),
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
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
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    project: Mapped[Project] = relationship(back_populates="tasks")
    assignee: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_to],
        back_populates="assigned_tasks",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="task",
        lazy="selectin",
    )
    diffs: Mapped[list["Diff"]] = relationship(
        "Diff",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="task",
        lazy="selectin",
    )
    review_reports: Mapped[list["ReviewReport"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    dependencies: Mapped[list[TaskDependency]] = relationship(
        foreign_keys=[TaskDependency.task_id],
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
        passive_deletes=True,
    )
    dependents: Mapped[list[TaskDependency]] = relationship(
        foreign_keys=[TaskDependency.depends_on_task_id],
        back_populates="depends_on",
        lazy="selectin",
        passive_deletes=True,
    )
