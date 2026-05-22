"""Platform Expansion — multi-agent review, team management & integrations.

Creates 10 new tables:
  project_members, invitations,
  review_reports, review_comments,
  task_dependencies, task_templates,
  notifications,
  webhook_configs, webhook_deliveries,
  github_configs

Alters existing tables:
  tasks  — adds assigned_to, is_blocked
  users  — adds last_login_at (IF NOT EXISTS — safe for envs that pre-created the column)

Adds analytics indexes on agent_runs and tasks.

NOTE: idx_agent_runs_backend (coding_backend, status) from data-model.md is intentionally
omitted — the agent_runs table does not have a coding_backend column in the current schema.
Add that index in a later migration when/if coding_backend is added to agent_runs.

Revision ID: 005_platform_expansion
Revises: 014fb7e4d101
Create Date: 2026-05-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_platform_expansion"
down_revision: Union[str, None] = "014fb7e4d101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # project_members
    # ------------------------------------------------------------------
    op.create_table(
        "project_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
        sa.CheckConstraint(
            "role IN ('owner','leader','developer','viewer')",
            name="ck_project_members_role",
        ),
    )
    op.create_index("idx_project_members_project", "project_members", ["project_id"])
    op.create_index("idx_project_members_user", "project_members", ["user_id"])

    # ------------------------------------------------------------------
    # invitations
    # FIX-3: created_by / used_by use SET NULL so deleting a user does not
    #        block the DELETE — audit trail is preserved with NULL sentinel.
    # ------------------------------------------------------------------
    op.create_table(
        "invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invitee_email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token", name="uq_invitations_token"),
        sa.CheckConstraint(
            "role IN ('leader','developer','viewer')",
            name="ck_invitations_role",
        ),
    )
    op.create_index("idx_invitations_token", "invitations", ["token"])
    op.create_index("idx_invitations_project", "invitations", ["project_id"])

    # ------------------------------------------------------------------
    # review_reports
    # ------------------------------------------------------------------
    op.create_table(
        "review_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("suggestion", sa.String(20), nullable=True),
        sa.Column("test_runner", sa.String(50), nullable=True),
        sa.Column("test_pass", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("test_fail", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("test_error", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100",
            name="ck_review_reports_score",
        ),
        sa.CheckConstraint(
            "suggestion IN ('approve','needs_changes')",
            name="ck_review_reports_suggestion",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','complete','error')",
            name="ck_review_reports_status",
        ),
    )
    op.create_index("idx_review_reports_task", "review_reports", ["task_id"])

    # ------------------------------------------------------------------
    # review_comments
    # ------------------------------------------------------------------
    op.create_table(
        "review_comments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("review_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.String(10),
            server_default=sa.text("'info'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["review_report_id"], ["review_reports.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_review_comments_severity",
        ),
    )
    op.create_index("idx_review_comments_report", "review_comments", ["review_report_id"])

    # ------------------------------------------------------------------
    # task_dependencies
    # ------------------------------------------------------------------
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "task_id != depends_on_task_id",
            name="ck_task_dependencies_no_self",
        ),
    )
    op.create_index("idx_task_deps_task", "task_dependencies", ["task_id"])
    op.create_index("idx_task_deps_depends_on", "task_dependencies", ["depends_on_task_id"])

    # ------------------------------------------------------------------
    # task_templates
    # FIX-3: created_by uses SET NULL to allow user deletion without blocking.
    # FIX-2: UNIQUE(project_id, name) does not cover NULL project_id (global
    #        templates). A separate partial unique index enforces uniqueness
    #        for global-scope templates where project_id IS NULL.
    # ------------------------------------------------------------------
    op.create_table(
        "task_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("title_template", sa.String(255), nullable=False),
        sa.Column(
            "description_template",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.String(10),
            server_default=sa.text("'project'"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "name", name="uq_task_templates_project_name"),
        sa.CheckConstraint(
            "scope IN ('project','global')",
            name="ck_task_templates_scope",
        ),
    )
    # FIX-2: partial unique index for global templates (project_id IS NULL)
    op.create_index(
        "uq_task_templates_global_name",
        "task_templates",
        ["name"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )

    # ------------------------------------------------------------------
    # notifications
    # ------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reference_type", sa.String(20), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
        postgresql_where=sa.text("is_read = false"),
    )
    # FIX-4: use raw SQL for DESC-sorted composite index — op.create_index
    # does not reliably support sa.text() entries in the columns list.
    op.execute(sa.text(
        "CREATE INDEX idx_notifications_user "
        "ON notifications(user_id, created_at DESC)"
    ))

    # ------------------------------------------------------------------
    # webhook_configs
    # FIX-3: created_by uses SET NULL to allow user deletion.
    # ------------------------------------------------------------------
    op.create_table(
        "webhook_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("secret", sa.String(100), nullable=True),
        sa.Column(
            "events",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ------------------------------------------------------------------
    # webhook_deliveries
    # ------------------------------------------------------------------
    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("webhook_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column(
            "attempts",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["webhook_config_id"], ["webhook_configs.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('pending','success','failed','retrying')",
            name="ck_webhook_deliveries_status",
        ),
    )
    op.create_index(
        "idx_webhook_deliveries_config", "webhook_deliveries", ["webhook_config_id"]
    )
    op.create_index(
        "idx_webhook_deliveries_status",
        "webhook_deliveries",
        ["status"],
        postgresql_where=sa.text("status IN ('pending','retrying')"),
    )

    # ------------------------------------------------------------------
    # github_configs
    # FIX-3: created_by uses SET NULL to allow user deletion.
    # ------------------------------------------------------------------
    op.create_table(
        "github_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repo_full_name", sa.String(200), nullable=False),
        sa.Column("pat_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "default_base_branch",
            sa.String(100),
            server_default=sa.text("'main'"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", name="uq_github_configs_project"),
    )

    # ------------------------------------------------------------------
    # ALTER tasks — add assigned_to, is_blocked
    # ------------------------------------------------------------------
    op.add_column(
        "tasks",
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_tasks_assigned_to_users",
        "tasks",
        "users",
        ["assigned_to"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_tasks_assigned_to", "tasks", ["assigned_to"])

    # ------------------------------------------------------------------
    # ALTER users — add last_login_at
    # FIX-1: Use raw SQL with IF NOT EXISTS to be idempotent in case the
    # column was already added manually on any environment.
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "last_login_at TIMESTAMPTZ"
    ))

    # ------------------------------------------------------------------
    # Analytics indexes
    # agent_runs uses started_at (not created_at).
    # idx_agent_runs_backend (coding_backend, status) is intentionally
    # omitted — agent_runs has no coding_backend column yet; add when
    # that column is introduced.
    # ------------------------------------------------------------------
    op.create_index(
        "idx_agent_runs_project_status",
        "agent_runs",
        ["project_id", "status", "started_at"],
    )
    op.create_index(
        "idx_tasks_project_status_updated",
        "tasks",
        ["project_id", "status", "updated_at"],
    )


def downgrade() -> None:
    # analytics indexes
    op.drop_index("idx_tasks_project_status_updated", table_name="tasks")
    op.drop_index("idx_agent_runs_project_status", table_name="agent_runs")

    # ALTER users
    op.drop_column("users", "last_login_at")

    # ALTER tasks
    op.drop_index("idx_tasks_assigned_to", table_name="tasks")
    op.drop_constraint("fk_tasks_assigned_to_users", "tasks", type_="foreignkey")
    op.drop_column("tasks", "is_blocked")
    op.drop_column("tasks", "assigned_to")

    # new tables (reverse order of FK deps)
    op.drop_table("github_configs")
    op.drop_index("idx_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_config", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_configs")
    op.execute(sa.text("DROP INDEX IF EXISTS idx_notifications_user"))
    op.drop_index("idx_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("uq_task_templates_global_name", table_name="task_templates")
    op.drop_table("task_templates")
    op.drop_index("idx_task_deps_depends_on", table_name="task_dependencies")
    op.drop_index("idx_task_deps_task", table_name="task_dependencies")
    op.drop_table("task_dependencies")
    op.drop_index("idx_review_comments_report", table_name="review_comments")
    op.drop_table("review_comments")
    op.drop_index("idx_review_reports_task", table_name="review_reports")
    op.drop_table("review_reports")
    op.drop_index("idx_invitations_project", table_name="invitations")
    op.drop_index("idx_invitations_token", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("idx_project_members_user", table_name="project_members")
    op.drop_index("idx_project_members_project", table_name="project_members")
    op.drop_table("project_members")
