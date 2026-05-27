"""Replace per-project WIP index with per-assignee index for multi-user mode.

Revision ID: 006_wip_per_developer_index
Revises: 005_platform_expansion
Create Date: 2026-05-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_wip_per_developer_index"
down_revision: Union[str, None] = "005_platform_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("one_in_progress_per_project", table_name="tasks")
    op.create_index(
        "one_in_progress_per_assignee",
        "tasks",
        ["project_id", "assigned_to"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress' AND assigned_to IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("one_in_progress_per_assignee", table_name="tasks")
    op.create_index(
        "one_in_progress_per_project",
        "tasks",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )
