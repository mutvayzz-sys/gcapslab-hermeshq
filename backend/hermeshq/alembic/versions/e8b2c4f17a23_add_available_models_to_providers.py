"""add available_models to providers

Revision ID: e8b2c4f17a23
Revises: c7a3f8d29e14
Create Date: 2026-05-27 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e8b2c4f17a23'
down_revision: Union[str, None] = 'c7a3f8d29e14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("providers", "available_models"):
        op.add_column(
            "providers",
            sa.Column("available_models", JSONB, nullable=True, server_default="[]"),
        )


def downgrade() -> None:
    if _column_exists("providers", "available_models"):
        op.drop_column("providers", "available_models")
