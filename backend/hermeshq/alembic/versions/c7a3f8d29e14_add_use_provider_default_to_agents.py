"""add use_provider_default to agents

Revision ID: c7a3f8d29e14
Revises: 9a4ccb262336
Create Date: 2026-05-27 17:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'c7a3f8d29e14'
down_revision: str | None = '9a4ccb262336'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column already exists in the given table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("agents", "use_provider_default"):
        op.add_column(
            "agents",
            sa.Column("use_provider_default", sa.Boolean(), nullable=True),
        )
        # Set default to True for all existing agents (they were using the
        # model column as their effective model, which at creation time came
        # from the provider default — so opt them in to tracking changes).
        op.execute("UPDATE agents SET use_provider_default = TRUE")
        # Now make it NOT NULL with a server default for new rows.
        op.alter_column(
            "agents",
            "use_provider_default",
            nullable=False,
            server_default=sa.text("TRUE"),
        )


def downgrade() -> None:
    if _column_exists("agents", "use_provider_default"):
        op.drop_column("agents", "use_provider_default")
