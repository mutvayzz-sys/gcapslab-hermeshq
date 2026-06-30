"""restore runtime containers table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-28 19:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _table_exists("runtime_containers"):
        return
    op.create_table(
        "runtime_containers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("container_name", sa.String(length=128), nullable=False),
        sa.Column("image", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("endpoint_path", sa.String(length=255), nullable=False),
        sa.Column("api_server_key", sa.String(length=128), nullable=False),
        sa.Column("health_status", sa.String(length=24), nullable=True),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runtime_containers_user_id", "runtime_containers", ["user_id"])
    op.create_index("ix_runtime_containers_organization_id", "runtime_containers", ["organization_id"])
    op.create_index("ix_runtime_containers_agent_id", "runtime_containers", ["agent_id"])
    op.create_index("ix_runtime_containers_container_name", "runtime_containers", ["container_name"], unique=True)
    op.create_index("ix_runtime_containers_status", "runtime_containers", ["status"])


def downgrade() -> None:
    if _table_exists("runtime_containers"):
        op.drop_table("runtime_containers")
