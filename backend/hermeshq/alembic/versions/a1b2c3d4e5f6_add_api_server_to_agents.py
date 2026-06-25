"""add api_server fields to agents

Revision ID: a1b2c3d4e5f6
Revises: f5a7d3e29b18
Create Date: 2026-06-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f5a7d3e29b18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("agents", "api_server_enabled"):
        op.add_column(
            "agents",
            sa.Column("api_server_enabled", sa.Boolean, nullable=False, server_default="false"),
        )
    if not _column_exists("agents", "api_port"):
        op.add_column(
            "agents",
            sa.Column("api_port", sa.Integer, nullable=True),
        )
        op.create_unique_constraint("uq_agents_api_port", "agents", ["api_port"])
    if not _column_exists("agents", "api_server_key"):
        op.add_column(
            "agents",
            sa.Column("api_server_key", sa.String(128), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("agents", "api_server_key"):
        op.drop_column("agents", "api_server_key")
    if _column_exists("agents", "api_port"):
        op.drop_constraint("uq_agents_api_port", "agents", type_="unique")
        op.drop_column("agents", "api_port")
    if _column_exists("agents", "api_server_enabled"):
        op.drop_column("agents", "api_server_enabled")
