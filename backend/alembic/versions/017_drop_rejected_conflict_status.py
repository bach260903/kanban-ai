"""Drop 'rejected' and 'conflict' from task status — board uses 4 statuses only.

Existing rows in those states are normalised back to 'todo' (a failed coder run
now returns the task to To do; a merge conflict already set the task to 'todo'
and only the task_branch row carries the 'conflict' state).

Revision ID: 017_drop_rejected_conflict
Revises: 016_devops_monitoring
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op

revision = "017_drop_rejected_conflict"
down_revision = "016_devops_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalise any existing rows before tightening the constraint.
    op.execute(
        "UPDATE tasks SET status = 'todo' WHERE status IN ('rejected', 'conflict')"
    )
    op.drop_constraint("ck_tasks_status", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_status",
        "tasks",
        "status IN ('todo','in_progress','review','done')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tasks_status", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_status",
        "tasks",
        "status IN ('todo','in_progress','review','done','rejected','conflict')",
    )
