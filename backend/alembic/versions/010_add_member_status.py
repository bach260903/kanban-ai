"""Add status column to project_members for pending approval flow.

Revision ID: 010_add_member_status
Revises: 009_drop_project_name_unique
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010_add_member_status"
down_revision = "009_drop_project_name_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_members",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_check_constraint(
        "ck_project_members_status",
        "project_members",
        "status IN ('active', 'pending')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_project_members_status", "project_members", type_="check")
    op.drop_column("project_members", "status")
