"""add created_by_user_id to tasks

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [col["name"] for col in insp.get_columns(table_name)]
    return column_name in columns


def _index_exists(index_name: str, table_name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    if not _column_exists("tasks", "created_by_user_id"):
        op.add_column(
            "tasks",
            sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
    if not _index_exists("ix_tasks_created_by_user_id", "tasks"):
        op.create_index("ix_tasks_created_by_user_id", "tasks", ["created_by_user_id"])


def downgrade() -> None:
    if _index_exists("ix_tasks_created_by_user_id", "tasks"):
        op.drop_index("ix_tasks_created_by_user_id", table_name="tasks")
    if _column_exists("tasks", "created_by_user_id"):
        op.drop_column("tasks", "created_by_user_id")
