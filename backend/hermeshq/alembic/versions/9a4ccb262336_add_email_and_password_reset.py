"""add_email_and_password_reset

Revision ID: 9a4ccb262336
Revises: 8cc23c178ece
Create Date: 2026-05-25 20:56:04.587450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a4ccb262336'
down_revision: Union[str, None] = '8cc23c178ece'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Email config fields on app_settings
    op.add_column('app_settings', sa.Column('resend_api_key', sa.String(255), nullable=True))
    op.add_column('app_settings', sa.Column('from_email', sa.String(255), nullable=True))
    op.add_column('app_settings', sa.Column('from_name', sa.String(128), nullable=True))
    op.add_column('app_settings', sa.Column('public_base_url', sa.String(512), nullable=True))

    # Password reset tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_password_reset_tokens_user_id', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    op.drop_column('app_settings', 'public_base_url')
    op.drop_column('app_settings', 'from_name')
    op.drop_column('app_settings', 'from_email')
    op.drop_column('app_settings', 'resend_api_key')
