"""Persisted thought stream / tool events (Phase 2 / US10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StreamEventType(StrEnum):
    THOUGHT = "THOUGHT"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    ACTION = "ACTION"
    ERROR = "ERROR"
    STATUS_CHANGE = "STATUS_CHANGE"


class StreamEvent(Base):
    __tablename__ = "stream_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('THOUGHT','TOOL_CALL','TOOL_RESULT','ACTION','ERROR','STATUS_CHANGE')",
            name="ck_stream_events_event_type",
        ),
        UniqueConstraint("task_id", "sequence_number", name="uq_stream_events_task_sequence"),
        Index("idx_stream_events_task_seq", "task_id", "sequence_number"),
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
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[StreamEventType] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    task: Mapped["Task"] = relationship("Task", foreign_keys=[task_id])
    agent_run: Mapped["AgentRun | None"] = relationship("AgentRun", foreign_keys=[agent_run_id])
