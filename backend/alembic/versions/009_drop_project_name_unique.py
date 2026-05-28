"""Drop global unique constraint on projects.name.

Projects are multi-user; different users should be able to create projects
with the same name. Identity is via UUID, not name.

Revision ID: 009_drop_project_name_unique
Revises: 008_merge_wip_oauth_heads
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_drop_project_name_unique"
down_revision: Union[str, Sequence[str], None] = "008_merge_wip_oauth_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_projects_name", "projects", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_projects_name", "projects", ["name"])
