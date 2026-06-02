"""add check constraints for status columns

Revision ID: b1c2d3e4f5a6
Revises: a3b4c5d6e7f8
Create Date: 2026-06-02 14:47:00.000000

"""
from alembic import op
from sqlalchemy import inspect


revision = "b1c2d3e4f5a6"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check whether a CHECK constraint already exists on the table."""
    bind = op.get_bind()
    insp = inspect(bind)
    # get_check_constraints returns list of dicts with 'name' key
    checks = insp.get_check_constraints(table_name)
    return any(c["name"] == constraint_name for c in checks)


def upgrade() -> None:
    if not _constraint_exists("agents", "ck_agents_status"):
        op.create_check_constraint(
            "ck_agents_status",
            "agents",
            "status IN ('stopped', 'running', 'error', 'starting')",
        )

    if not _constraint_exists("tasks", "ck_tasks_status"):
        op.create_check_constraint(
            "ck_tasks_status",
            "tasks",
            "status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')",
        )


def downgrade() -> None:
    if _constraint_exists("agents", "ck_agents_status"):
        op.drop_constraint("ck_agents_status", "agents", type_="check")

    if _constraint_exists("tasks", "ck_tasks_status"):
        op.drop_constraint("ck_tasks_status", "tasks", type_="check")
