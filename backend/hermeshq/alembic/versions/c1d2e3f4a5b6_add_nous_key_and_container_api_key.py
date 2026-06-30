"""add nous_api_key to organizations and api_server_key to containers

Revision ID: c1d2e3f4a5b6
Revises: b3c4d5e6f7a8
Create Date: 2026-06-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    # Table may not exist yet (e.g. containers table is created by a later migration)
    if not insp.has_table(table_name):
        return False
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("organizations", "nous_api_key"):
        op.add_column("organizations", sa.Column("nous_api_key", sa.String(255), nullable=True))
    if not _column_exists("organizations", "nous_base_url"):
        op.add_column("organizations", sa.Column("nous_base_url", sa.String(512), nullable=True))
    if not _column_exists("containers", "api_server_key"):
        op.add_column("containers", sa.Column("api_server_key", sa.String(128), nullable=True))


def downgrade() -> None:
    if _column_exists("containers", "api_server_key"):
        op.drop_column("containers", "api_server_key")
    if _column_exists("organizations", "nous_base_url"):
        op.drop_column("organizations", "nous_base_url")
    if _column_exists("organizations", "nous_api_key"):
        op.drop_column("organizations", "nous_api_key")
