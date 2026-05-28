"""Phase 3: step_failure_analyses table + pipeline_steps retry columns.

Revision ID: 015_failure_analysis
Revises: 013_deployment_phase2
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "015_failure_analysis"
down_revision = "013_deployment_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: step_failure_analyses ──────────────────────────────────────
    op.create_table(
        "step_failure_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # AI analysis
        sa.Column("root_cause", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("fix_strategy", sa.Text, nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default=sa.text("'low'")),
        sa.Column("is_auto_fixable", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("human_approval_required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        # Patch outcome
        sa.Column("patch_applied", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("patch_summary", sa.Text, nullable=True),
        # Retry
        sa.Column("retry_triggered", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("retry_attempt", sa.Integer, nullable=False, server_default=sa.text("0")),
        # Approval
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        # Trace
        sa.Column("ai_prompt_snippet", sa.Text, nullable=True),
        sa.Column("ai_raw_response", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_failure_analysis_step", "step_failure_analyses", ["step_id"])
    op.create_index("idx_failure_analysis_run", "step_failure_analyses", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_failure_analysis_run", table_name="step_failure_analyses")
    op.drop_index("idx_failure_analysis_step", table_name="step_failure_analyses")
    op.drop_table("step_failure_analyses")
