"""Cached codebase structure map (Phase 2 / US14)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CodebaseMap(Base):
    __tablename__ = "codebase_maps"

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
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    map_json: Mapped[Any] = mapped_column(JSONB(astext_type=Text()), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship("Project", foreign_keys=[project_id])
    task: Mapped["Task | None"] = relationship("Task", foreign_keys=[task_id])
