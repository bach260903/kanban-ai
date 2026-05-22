"""Add coding_backend column to projects.

Revision ID: 004_add_coding_backend
Revises: 003_add_users
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_add_coding_backend"
down_revision: Union[str, None] = "003_add_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "coding_backend",
            sa.String(length=20),
            nullable=False,
            server_default="groq",
        ),
    )
    op.create_check_constraint(
        "ck_projects_coding_backend",
        "projects",
        "coding_backend IN ('groq', 'claude_code', 'openai', 'gemini')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_projects_coding_backend", "projects", type_="check")
    op.drop_column("projects", "coding_backend")
