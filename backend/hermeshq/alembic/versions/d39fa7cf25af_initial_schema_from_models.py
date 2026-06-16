"""initial_schema_from_models

Revision ID: d39fa7cf25af
Revises:
Create Date: 2026-05-22 17:37:04.947999

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd39fa7cf25af'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use the synchronous connection from op.get_bind() to create all tables
    # from the SQLAlchemy declarative metadata.  This is safe for both fresh
    # installs (creates tables) and existing databases (create_all is a no-op
    # for tables that already exist).
    import hermeshq.models  # noqa: F401 — registers all models on Base.metadata
    from hermeshq.models.base import Base

    connection = op.get_bind()
    Base.metadata.create_all(bind=connection)


def downgrade() -> None:
    # Drop all tables (for complete teardown — use with caution)
    import hermeshq.models  # noqa: F401
    from hermeshq.models.base import Base

    connection = op.get_bind()
    Base.metadata.drop_all(bind=connection)
