"""add created_by_user_id to tasks

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if not conn.dialect.has_table(conn, "tasks"):
        return
    columns = [row["name"] for row in conn.execute(sa.text("SELECT column_name AS name FROM information_schema.columns WHERE table_name='tasks'")).mappings().all()]
    if "created_by_user_id" not in columns:
        op.add_column(
            "tasks",
            sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_tasks_created_by_user_id", "tasks", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_created_by_user_id", table_name="tasks")
    op.drop_column("tasks", "created_by_user_id")
