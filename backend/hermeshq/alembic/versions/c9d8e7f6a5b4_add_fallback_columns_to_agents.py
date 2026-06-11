"""add fallback columns to agents

Revision ID: c9d8e7f6a5b4
Revises: a1b2c3d4e5f6
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c9d8e7f6a5b4"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("agents", "fallback_provider"):
        op.add_column("agents", sa.Column("fallback_provider", sa.String(64), nullable=True))
    if not _column_exists("agents", "fallback_model"):
        op.add_column("agents", sa.Column("fallback_model", sa.String(255), nullable=True))
    if not _column_exists("agents", "fallback_api_key_ref"):
        op.add_column("agents", sa.Column("fallback_api_key_ref", sa.String(128), nullable=True))
    if not _column_exists("agents", "fallback_base_url"):
        op.add_column("agents", sa.Column("fallback_base_url", sa.String(512), nullable=True))


def downgrade() -> None:
    if _column_exists("agents", "fallback_base_url"):
        op.drop_column("agents", "fallback_base_url")
    if _column_exists("agents", "fallback_api_key_ref"):
        op.drop_column("agents", "fallback_api_key_ref")
    if _column_exists("agents", "fallback_model"):
        op.drop_column("agents", "fallback_model")
    if _column_exists("agents", "fallback_provider"):
        op.drop_column("agents", "fallback_provider")
