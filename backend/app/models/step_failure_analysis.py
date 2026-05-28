"""Step failure analysis ORM model — Phase 3 AI self-healing."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_step import PipelineStep


class StepFailureAnalysis(Base):
    """AI-generated failure analysis for a single failed pipeline step.

    One row per failure event.  A retried step may accumulate multiple rows.
    """

    __tablename__ = "step_failure_analyses"
    __table_args__ = (
        Index("idx_failure_analysis_step", "step_id"),
        Index("idx_failure_analysis_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_steps.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── AI analysis output ─────────────────────────────────────────────────────
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fix_strategy: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'low'"),
        comment="low | medium | high",
    )
    is_auto_fixable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── Auto-fix outcome ───────────────────────────────────────────────────────
    patch_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    patch_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Retry tracking ─────────────────────────────────────────────────────────
    retry_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_attempt: Mapped[int] = mapped_column(
        nullable=False, default=0,
        comment="Attempt number of the retry step (0 = no retry)",
    )

    # ── Human approval (for dangerous fixes) ──────────────────────────────────
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Observability / AI trace ──────────────────────────────────────────────
    ai_prompt_snippet: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="First 2000 chars of the analysis prompt"
    )
    ai_raw_response: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Raw JSON string from the LLM"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    step: Mapped["PipelineStep"] = relationship(
        "PipelineStep",
        back_populates="failure_analyses",
    )
