"""Merge migration heads after platform expansion.

Revision ID: 008_merge_wip_oauth_heads
Revises: 006_wip_per_developer_index, 007_auth_oauth_fields
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "008_merge_wip_oauth_heads"
down_revision: Union[str, Sequence[str], None] = (
    "006_wip_per_developer_index",
    "007_auth_oauth_fields",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

