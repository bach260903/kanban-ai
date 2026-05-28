"""Phase 4: DevOps monitoring — health checks, incidents, rollbacks, alert config.

Revision ID: 016_devops_monitoring
Revises: 015_failure_analysis
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "016_devops_monitoring"
down_revision = "015_failure_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend deployments ────────────────────────────────────────────────────
    op.add_column("deployments", sa.Column(
        "health_status", sa.String(20), nullable=True,
        comment="unknown | healthy | degraded | critical",
    ))
    op.add_column("deployments", sa.Column(
        "rollback_of_id", postgresql.UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        "fk_deployments_rollback_of",
        "deployments", "deployments",
        ["rollback_of_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── Extend deployment_configs (alert webhooks + health check) ─────────────
    op.add_column("deployment_configs", sa.Column(
        "discord_webhook_url", sa.Text, nullable=True,
    ))
    op.add_column("deployment_configs", sa.Column(
        "slack_webhook_url", sa.Text, nullable=True,
    ))
    op.add_column("deployment_configs", sa.Column(
        "health_check_path", sa.String(255), nullable=True,
        server_default=sa.text("'/health'"),
        comment="Path to poll for health checks (default: /health)",
    ))
    op.add_column("deployment_configs", sa.Column(
        "alert_on_anomaly", sa.Boolean, nullable=False,
        server_default=sa.text("true"),
    ))
    op.add_column("deployment_configs", sa.Column(
        "monitor_duration_minutes", sa.Integer, nullable=False,
        server_default=sa.text("5"),
        comment="How long to monitor after deploy (minutes)",
    ))

    # ── New table: deployment_health_checks ───────────────────────────────────
    op.create_table(
        "deployment_health_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("http_status", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("response_snippet", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("idx_dhc_deployment", "deployment_health_checks", ["deployment_id"])
    op.create_index("idx_dhc_project", "deployment_health_checks", ["project_id"])

    # ── New table: deployment_incidents ───────────────────────────────────────
    op.create_table(
        "deployment_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("risk_score", sa.Float, nullable=True),
        sa.Column("metric_snapshot", sa.Text, nullable=True),
        sa.Column("rollback_triggered", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("idx_incident_deployment", "deployment_incidents", ["deployment_id"])
    op.create_index("idx_incident_project", "deployment_incidents", ["project_id"])

    # ── New table: rollback_events ────────────────────────────────────────────
    op.create_table(
        "rollback_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("deployment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.String(20), nullable=False,
                  server_default=sa.text("'manual'")),
        sa.Column("previous_deployment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("alert_sent", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("idx_rollback_deployment", "rollback_events", ["deployment_id"])
    op.create_index("idx_rollback_project", "rollback_events", ["project_id"])


def downgrade() -> None:
    op.drop_index("idx_rollback_project", table_name="rollback_events")
    op.drop_index("idx_rollback_deployment", table_name="rollback_events")
    op.drop_table("rollback_events")

    op.drop_index("idx_incident_project", table_name="deployment_incidents")
    op.drop_index("idx_incident_deployment", table_name="deployment_incidents")
    op.drop_table("deployment_incidents")

    op.drop_index("idx_dhc_project", table_name="deployment_health_checks")
    op.drop_index("idx_dhc_deployment", table_name="deployment_health_checks")
    op.drop_table("deployment_health_checks")

    op.drop_column("deployment_configs", "monitor_duration_minutes")
    op.drop_column("deployment_configs", "alert_on_anomaly")
    op.drop_column("deployment_configs", "health_check_path")
    op.drop_column("deployment_configs", "slack_webhook_url")
    op.drop_column("deployment_configs", "discord_webhook_url")

    op.drop_constraint("fk_deployments_rollback_of", "deployments", type_="foreignkey")
    op.drop_column("deployments", "rollback_of_id")
    op.drop_column("deployments", "health_status")
