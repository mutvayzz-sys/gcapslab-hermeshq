"""add auxiliary_models to agents

Revision ID: f5a7d3e29b18
Revises: e8b2c4f17a23
Create Date: 2026-05-28 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f5a7d3e29b18'
down_revision: Union[str, None] = 'e8b2c4f17a23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("agents", "auxiliary_models"):
        op.add_column(
            "agents",
            sa.Column("auxiliary_models", sa.JSON, nullable=True),
        )


def downgrade() -> None:
    if _column_exists("agents", "auxiliary_models"):
        op.drop_column("agents", "auxiliary_models")
