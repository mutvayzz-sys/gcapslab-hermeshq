"""add organizations table

Revision ID: 5aaebcf3706f
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "5aaebcf3706f"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table_name in insp.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    # Create organizations table
    if not _table_exists("organizations"):
        op.create_table(
            "organizations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False, server_default="company"),
            sa.Column("default_mode", sa.String(16), nullable=True),
            sa.Column("default_capabilities", sa.String(255), nullable=True),
            sa.Column("system_prompt_override", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Add organization_id to users table
    if not _column_exists("users", "organization_id"):
        op.add_column(
            "users",
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
        )
        op.create_index("ix_users_organization_id", "users", ["organization_id"])


def downgrade() -> None:
    if _index_exists("users", "ix_users_organization_id"):
        op.drop_index("ix_users_organization_id", table_name="users")
    if _column_exists("users", "organization_id"):
        op.drop_column("users", "organization_id")
    if _table_exists("organizations"):
        op.drop_index("ix_organizations_slug", table_name="organizations")
        op.drop_table("organizations")
