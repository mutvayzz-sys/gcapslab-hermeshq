"""add messaging channel ids to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    if not _column_exists("users", "telegram_id"):
        op.add_column("users", sa.Column("telegram_id", sa.String(128), nullable=True))
    if not _column_exists("users", "whatsapp_user"):
        op.add_column("users", sa.Column("whatsapp_user", sa.String(128), nullable=True))
    if not _column_exists("users", "teams_id"):
        op.add_column("users", sa.Column("teams_id", sa.String(255), nullable=True))
    if not _column_exists("users", "google_chat_email"):
        op.add_column("users", sa.Column("google_chat_email", sa.String(255), nullable=True))
    if not _column_exists("users", "kapso_id"):
        op.add_column("users", sa.Column("kapso_id", sa.String(128), nullable=True))
    if not _column_exists("users", "kapso_number"):
        op.add_column("users", sa.Column("kapso_number", sa.String(64), nullable=True))

    if not _index_exists("users", "ix_users_telegram_id"):
        op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    if not _index_exists("users", "ix_users_whatsapp_user"):
        op.create_index("ix_users_whatsapp_user", "users", ["whatsapp_user"])
    if not _index_exists("users", "ix_users_teams_id"):
        op.create_index("ix_users_teams_id", "users", ["teams_id"])
    if not _index_exists("users", "ix_users_google_chat_email"):
        op.create_index("ix_users_google_chat_email", "users", ["google_chat_email"])
    if not _index_exists("users", "ix_users_kapso_id"):
        op.create_index("ix_users_kapso_id", "users", ["kapso_id"])


def downgrade() -> None:
    if _index_exists("users", "ix_users_kapso_id"):
        op.drop_index("ix_users_kapso_id", table_name="users")
    if _index_exists("users", "ix_users_google_chat_email"):
        op.drop_index("ix_users_google_chat_email", table_name="users")
    if _index_exists("users", "ix_users_teams_id"):
        op.drop_index("ix_users_teams_id", table_name="users")
    if _index_exists("users", "ix_users_whatsapp_user"):
        op.drop_index("ix_users_whatsapp_user", table_name="users")
    if _index_exists("users", "ix_users_telegram_id"):
        op.drop_index("ix_users_telegram_id", table_name="users")

    if _column_exists("users", "kapso_number"):
        op.drop_column("users", "kapso_number")
    if _column_exists("users", "kapso_id"):
        op.drop_column("users", "kapso_id")
    if _column_exists("users", "google_chat_email"):
        op.drop_column("users", "google_chat_email")
    if _column_exists("users", "teams_id"):
        op.drop_column("users", "teams_id")
    if _column_exists("users", "whatsapp_user"):
        op.drop_column("users", "whatsapp_user")
    if _column_exists("users", "telegram_id"):
        op.drop_column("users", "telegram_id")
