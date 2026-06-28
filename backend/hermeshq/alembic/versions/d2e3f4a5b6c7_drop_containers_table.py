"""drop containers table

Revision ID: d2e3f4a5b6c7
Revises: a76ce3469848
Create Date: 2026-06-28 23:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "a76ce3469848"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _table_exists("containers"):
        op.drop_table("containers")


def downgrade() -> None:
    # We do not recreate the table on downgrade — the feature is intentionally
    # removed. A downgrade from this revision is a no-op for the table.
    pass
