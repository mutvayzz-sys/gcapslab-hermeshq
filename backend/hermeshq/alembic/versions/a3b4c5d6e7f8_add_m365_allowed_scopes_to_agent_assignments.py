"""add m365_allowed_scopes to agent_assignments

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("agent_assignments", "m365_allowed_scopes"):
        op.add_column(
            "agent_assignments",
            sa.Column("m365_allowed_scopes", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("agent_assignments", "m365_allowed_scopes"):
        op.drop_column("agent_assignments", "m365_allowed_scopes")
