"""Agent run ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.project import Project


class AgentType(StrEnum):
    ARCHITECT = "architect"
    CODER = "coder"
    REVIEWER = "reviewer"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    AWAITING_HIL = "awaiting_hil"
    PAUSED = "paused"
    TIMEOUT = "timeout"


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "agent_type IN ('architect','coder','reviewer')",
            name="ck_agent_runs_agent_type",
        ),
        CheckConstraint(
            "status IN ('running','success','failure','awaiting_hil','paused','timeout')",
            name="ck_agent_runs_status",
        ),
        Index("idx_agent_runs_task", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_type: Mapped[AgentType] = mapped_column(String(20), nullable=False)
    agent_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'1.0.0'"),
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'running'"),
    )
    input_artifacts: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    output_artifacts: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[Any | None] = mapped_column(JSONB(astext_type=Text()), nullable=True)

    task: Mapped["Task | None"] = relationship("Task", back_populates="agent_runs")
    project: Mapped[Project] = relationship(back_populates="agent_runs")
    diffs: Mapped[list["Diff"]] = relationship(
        "Diff",
        back_populates="agent_run",
        lazy="selectin",
    )
