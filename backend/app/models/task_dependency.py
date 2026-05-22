"""Task dependency (DAG edge) model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import Task


class TaskDependency(Base):
    """Directed dependency: task_id depends on depends_on_task_id."""

    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint(
            "task_id != depends_on_task_id",
            name="ck_task_dependencies_no_self",
        ),
        Index("idx_task_deps_task", "task_id"),
        Index("idx_task_deps_depends_on", "depends_on_task_id"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    task: Mapped["Task"] = relationship(
        foreign_keys=[task_id],
        back_populates="dependencies",
    )
    depends_on: Mapped["Task"] = relationship(
        foreign_keys=[depends_on_task_id],
        back_populates="dependents",
    )
