"""merge migration heads

Revision ID: 014fb7e4d101
Revises: 004_add_coding_backend, 004_auto_dispatch
Create Date: 2026-05-22 20:52:13.004131

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014fb7e4d101'
down_revision: Union[str, None] = ('004_add_coding_backend', '004_auto_dispatch')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
