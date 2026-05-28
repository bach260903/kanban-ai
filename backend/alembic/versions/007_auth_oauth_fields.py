"""Add github_id, avatar_url to users; make hashed_password nullable.

Revision ID: 007_auth_oauth_fields
Revises: 005_platform_expansion
Create Date: 2026-05-27

Changes:
  users
    - hashed_password  VARCHAR(255) NOT NULL  →  nullable
    - +github_id       VARCHAR(50)  UNIQUE NULLABLE  (GitHub OAuth identity)
    - +avatar_url      TEXT         NULLABLE
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_auth_oauth_fields"
down_revision: Union[str, None] = "005_platform_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Allow hashed_password to be NULL for OAuth-only accounts
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(255),
        nullable=True,
    )

    # GitHub OAuth identity (unique — one GitHub account per user)
    op.add_column(
        "users",
        sa.Column("github_id", sa.String(50), nullable=True),
    )
    op.create_unique_constraint("uq_users_github_id", "users", ["github_id"])
    op.create_index("idx_users_github_id", "users", ["github_id"])

    # Profile avatar from GitHub (or future providers)
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_index("idx_users_github_id", table_name="users")
    op.drop_constraint("uq_users_github_id", "users", type_="unique")
    op.drop_column("users", "github_id")

    # Re-apply NOT NULL — will fail if any row has NULL hashed_password.
    # Run: UPDATE users SET hashed_password='' WHERE hashed_password IS NULL;  first.
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(255),
        nullable=False,
    )
