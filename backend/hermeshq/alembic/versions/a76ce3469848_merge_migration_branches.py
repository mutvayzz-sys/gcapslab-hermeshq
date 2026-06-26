"""merge_migration_branches

Revision ID: a76ce3469848
Revises: c1d2e3f4a5b6, e2f3a4b5c6d7
Create Date: 2026-06-26 12:54:56.546880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a76ce3469848'
down_revision: Union[str, None] = ('c1d2e3f4a5b6', 'e2f3a4b5c6d7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
