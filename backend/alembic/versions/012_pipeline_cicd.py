"""Add pipeline_runs, pipeline_steps, deployments tables for CI/CD MVP.

Revision ID: 012_pipeline_cicd
Revises: 011_webhook_response_body
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "012_pipeline_cicd"
down_revision = "011_webhook_response_body"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pipeline_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("triggered_by", sa.String(100), nullable=True),
        sa.Column("branch_name", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('queued','running','success','failure','cancelled')",
            name="ck_pipeline_runs_status",
        ),
    )
    op.create_index("idx_pipeline_runs_project", "pipeline_runs", ["project_id"])
    op.create_index("idx_pipeline_runs_task", "pipeline_runs", ["task_id"])

    # ── pipeline_steps ─────────────────────────────────────────────────────────
    op.create_table(
        "pipeline_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("logs", sa.Text, nullable=True),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending','running','success','failure','skipped')",
            name="ck_pipeline_steps_status",
        ),
    )
    op.create_index("idx_pipeline_steps_run", "pipeline_steps", ["run_id"])

    # ── deployments ────────────────────────────────────────────────────────────
    op.create_table(
        "deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("preview_url", sa.String(500), nullable=True),
        sa.Column("risk_score", sa.Numeric(4, 2), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending','deploying','healthy','degraded','rolled_back','skipped')",
            name="ck_deployments_status",
        ),
    )
    op.create_index("idx_deployments_project", "deployments", ["project_id"])
    op.create_index("idx_deployments_task", "deployments", ["task_id"])
    op.create_index("idx_deployments_run", "deployments", ["run_id"])


def downgrade() -> None:
    op.drop_table("deployments")
    op.drop_table("pipeline_steps")
    op.drop_table("pipeline_runs")
