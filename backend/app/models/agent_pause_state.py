"""Per-task pause / resume state (Phase 2 / US10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PauseRunState(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"


class AgentPauseState(Base):
    __tablename__ = "agent_pause_states"
    __table_args__ = (
        CheckConstraint("state IN ('running','paused')", name="ck_agent_pause_states_state"),
        UniqueConstraint("task_id", name="uq_agent_pause_states_task_id"),
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
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id"),
        nullable=False,
    )
    state: Mapped[PauseRunState] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'running'"),
    )
    steering_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    task: Mapped["Task"] = relationship("Task", foreign_keys=[task_id])
    agent_run: Mapped["AgentRun"] = relationship("AgentRun", foreign_keys=[agent_run_id])
