"""add m365 user tokens and app config

Revision ID: e1f2a3b4c5d6
Revises: c7a3f8d29e14
Create Date: 2026-05-28 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "f5a7d3e29b18"
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


def upgrade() -> None:
    if not _table_exists("user_m365_tokens"):
        op.create_table(
            "user_m365_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False),
            sa.Column("account_email", sa.String(255), nullable=False),
            sa.Column("account_name", sa.String(255), nullable=True),
            sa.Column("token_cache_enc", sa.LargeBinary(), nullable=False),
            sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _column_exists("app_settings", "m365_client_id"):
        op.add_column("app_settings", sa.Column("m365_client_id", sa.String(255), nullable=True))
    if not _column_exists("app_settings", "m365_tenant_id"):
        op.add_column("app_settings", sa.Column("m365_tenant_id", sa.String(255), nullable=True))
    if not _column_exists("app_settings", "m365_enabled_scopes"):
        op.add_column("app_settings", sa.Column("m365_enabled_scopes", sa.JSON(), nullable=True, server_default="[]"))


def downgrade() -> None:
    if _column_exists("app_settings", "m365_enabled_scopes"):
        op.drop_column("app_settings", "m365_enabled_scopes")
    if _column_exists("app_settings", "m365_tenant_id"):
        op.drop_column("app_settings", "m365_tenant_id")
    if _column_exists("app_settings", "m365_client_id"):
        op.drop_column("app_settings", "m365_client_id")
    if _table_exists("user_m365_tokens"):
        op.drop_table("user_m365_tokens")
