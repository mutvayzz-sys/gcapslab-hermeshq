"""add mfa email support

Revision ID: a1b2c3d4e5f6
Revises: f5a7d3e29b18
Create Date: 2026-06-10 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f5a7d3e29b18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create mfa_codes table
    op.create_table(
        "mfa_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.Index("ix_mfa_codes_user_id"), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Add mfa_email_enabled column to app_settings
    op.add_column(
        "app_settings",
        sa.Column("mfa_email_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mfa_codes")
    op.drop_column("app_settings", "mfa_email_enabled")
