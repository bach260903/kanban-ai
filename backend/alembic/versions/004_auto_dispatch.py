"""Add projects.auto_dispatch_enabled for automatic priority task dispatch.

Revision ID: 004_auto_dispatch
Revises: 002_phase2_schema
Create Date: 2026-05-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_auto_dispatch"
down_revision: Union[str, None] = "002_phase2_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "auto_dispatch_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "auto_dispatch_enabled")
