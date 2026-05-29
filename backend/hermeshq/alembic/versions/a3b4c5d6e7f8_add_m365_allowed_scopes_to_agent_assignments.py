"""add m365_allowed_scopes to agent_assignments

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_assignments",
        sa.Column("m365_allowed_scopes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_assignments", "m365_allowed_scopes")
