"""Add response_body column to webhook_deliveries for debugging 4xx/5xx errors.

Revision ID: 011_webhook_response_body
Revises: 010_add_member_status
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "011_webhook_response_body"
down_revision = "010_add_member_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "webhook_deliveries",
        sa.Column("response_body", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("webhook_deliveries", "response_body")
