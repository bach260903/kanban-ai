"""Phase 2: add provider columns to deployments, create deployment_configs table.

Revision ID: 013_deployment_phase2
Revises: 012_pipeline_cicd
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "013_deployment_phase2"
down_revision = "012_pipeline_cicd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend deployments ─────────────────────────────────────────────────────
    op.add_column("deployments", sa.Column("provider", sa.String(20), nullable=True))
    op.add_column("deployments", sa.Column("external_id", sa.String(255), nullable=True))
    op.add_column("deployments", sa.Column("environment", sa.String(20), nullable=True,
                                            server_default="preview"))
    op.add_column("deployments", sa.Column("deploy_logs", sa.Text, nullable=True))
    op.add_column("deployments", sa.Column("branch_name", sa.String(255), nullable=True))
    op.add_column("deployments", sa.Column("commit_sha", sa.String(40), nullable=True))
    op.add_column("deployments", sa.Column("duration_ms", sa.Integer, nullable=True))
    op.add_column("deployments", sa.Column("error_message", sa.Text, nullable=True))

    # ── deployment_configs ─────────────────────────────────────────────────────
    op.create_table(
        "deployment_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("token_encrypted", sa.Text, nullable=False),
        sa.Column("project_name", sa.String(255), nullable=False,
                  comment="Provider-side project name/ID"),
        sa.Column("team_id", sa.String(255), nullable=True,
                  comment="Vercel team ID or Railway team slug"),
        sa.Column("base_url", sa.String(500), nullable=True,
                  comment="Custom domain / preview base URL pattern"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "provider IN ('vercel','railway','none')",
            name="ck_deployment_configs_provider",
        ),
    )
    op.create_index("idx_deployment_configs_project", "deployment_configs", ["project_id"])


def downgrade() -> None:
    op.drop_table("deployment_configs")
    for col in ("provider", "external_id", "environment", "deploy_logs",
                "branch_name", "commit_sha", "duration_ms", "error_message"):
        op.drop_column("deployments", col)
