"""add mfa email support

Revision ID: a1b2c3d4e5f6
Revises: b1c2d3e4f5a6
Create Date: 2026-06-10 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS mfa_codes (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            code_hash VARCHAR(128) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            ip_address VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mfa_codes_user_id ON mfa_codes (user_id)"
    )
    op.execute("""
        ALTER TABLE app_settings
        ADD COLUMN IF NOT EXISTS mfa_email_enabled BOOLEAN NOT NULL DEFAULT false
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE app_settings DROP COLUMN IF EXISTS mfa_email_enabled")
    op.execute("DROP INDEX IF EXISTS ix_mfa_codes_user_id")
    op.execute("DROP TABLE IF EXISTS mfa_codes")
