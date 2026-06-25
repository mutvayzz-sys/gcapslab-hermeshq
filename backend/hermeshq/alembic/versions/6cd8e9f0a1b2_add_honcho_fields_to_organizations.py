"""add honcho fields to organizations

Revision ID: 6cd8e9f0a1b2
Revises: 5aaebcf3706f
Create Date: 2026-06-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "6cd8e9f0a1b2"
down_revision: str | None = "5aaebcf3706f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("organizations", "honcho_base_url"):
        op.add_column(
            "organizations",
            sa.Column("honcho_base_url", sa.String(255), nullable=True),
        )
    if not _column_exists("organizations", "honcho_jwt_secret"):
        op.add_column(
            "organizations",
            sa.Column("honcho_jwt_secret", sa.Text, nullable=True),
        )


def downgrade() -> None:
    if _column_exists("organizations", "honcho_jwt_secret"):
        op.drop_column("organizations", "honcho_jwt_secret")
    if _column_exists("organizations", "honcho_base_url"):
        op.drop_column("organizations", "honcho_base_url")
