"""Git branch tracking per task (Phase 2 / US15)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TaskBranchStatus(StrEnum):
    ACTIVE = "active"
    MERGED = "merged"
    CONFLICT = "conflict"


class TaskBranch(Base):
    __tablename__ = "task_branches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','merged','conflict')",
            name="ck_task_branches_status",
        ),
        UniqueConstraint("task_id", name="uq_task_branches_task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TaskBranchStatus] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'active'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship("Task", foreign_keys=[task_id])
