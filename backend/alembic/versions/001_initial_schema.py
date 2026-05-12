"""Phase 1 — initial schema (projects, documents, tasks, agent_runs, diffs, feedbacks, audit_logs, intents).

WIP=1: PostgreSQL ``EXCLUDE USING btree (...) WHERE (status = 'in_progress')`` requires
extra operator support for ``uuid`` on some installs. This migration enforces the same
invariant with a **partial unique index** on ``(project_id) WHERE status = 'in_progress'**
(see data-model.md).

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(length=50), nullable=False),
        sa.Column("constitution", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_projects_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_projects_name"),
    )

    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("type IN ('SPEC','PLAN')", name="ck_documents_type"),
        sa.CheckConstraint(
            "status IN ('draft','approved','revision_requested')",
            name="ck_documents_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_documents_project_type",
        "documents",
        ["project_id", "type"],
        unique=False,
    )

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="todo", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('todo','in_progress','review','done','rejected','conflict')",
            name="ck_tasks_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_tasks_project_status",
        "tasks",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "one_in_progress_per_project",
        "tasks",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )

    op.create_table(
        "agent_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_type", sa.String(length=20), nullable=False),
        sa.Column("agent_version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
        sa.Column(
            "input_artifacts",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "output_artifacts",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "agent_type IN ('architect','coder','reviewer')",
            name="ck_agent_runs_agent_type",
        ),
        sa.CheckConstraint(
            "status IN ('running','success','failure','awaiting_hil','paused','timeout')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_runs_task", "agent_runs", ["task_id"], unique=False)

    op.create_table(
        "diffs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=False),
        sa.Column("modified_content", sa.Text(), nullable=False),
        sa.Column(
            "files_affected",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("review_status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "review_status IN ('pending','approved','rejected')",
            name="ck_diffs_review_status",
        ),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "feedbacks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_type", sa.String(length=10), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reference_type IN ('document','task')",
            name="ck_feedbacks_reference_type",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(length=100), nullable=False),
        sa.Column("agent_version", sa.String(length=20), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "input_refs",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "output_refs",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("result", sa.String(length=15), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "result IN ('success','failure','awaiting_hil')",
            name="ck_audit_logs_result",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_audit_logs_project",
        "audit_logs",
        ["project_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_audit_logs_task",
        "audit_logs",
        ["task_id", "timestamp"],
        unique=False,
    )

    op.create_table(
        "intents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_intents_project_id", "intents", ["project_id"], unique=False)

    op.execute(
        sa.text("""
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
    )
    op.execute(
        sa.text("""
CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
""")
    )
    op.execute(
        sa.text("""
CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
""")
    )
    op.execute(
        sa.text("""
CREATE TRIGGER trg_tasks_updated_at
BEFORE UPDATE ON tasks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
""")
    )

    op.execute(
        sa.text("""
CREATE OR REPLACE FUNCTION audit_logs_block_delete()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs rows cannot be deleted';
END;
$$ LANGUAGE plpgsql;
""")
    )
    op.execute(
        sa.text("""
CREATE TRIGGER trg_audit_logs_block_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_logs_block_delete();
""")
    )
    op.execute(
        sa.text("""
CREATE OR REPLACE FUNCTION audit_logs_limit_update()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.result IS DISTINCT FROM 'awaiting_hil' THEN
    RAISE EXCEPTION 'audit_logs may only be updated when result = awaiting_hil (finalise path)';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
    )
    op.execute(
        sa.text("""
CREATE TRIGGER trg_audit_logs_limit_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_logs_limit_update();
""")
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_limit_update ON audit_logs"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS audit_logs_limit_update()"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_block_delete ON audit_logs"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS audit_logs_block_delete()"))

    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_projects_updated_at ON projects"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_updated_at()"))

    op.drop_index("idx_intents_project_id", table_name="intents")
    op.drop_table("intents")

    op.drop_index("idx_audit_logs_task", table_name="audit_logs")
    op.drop_index("idx_audit_logs_project", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_table("feedbacks")
    op.drop_table("diffs")

    op.drop_index("idx_agent_runs_task", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("one_in_progress_per_project", table_name="tasks")
    op.drop_index("idx_tasks_project_status", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("idx_documents_project_type", table_name="documents")
    op.drop_table("documents")

    op.drop_table("projects")
