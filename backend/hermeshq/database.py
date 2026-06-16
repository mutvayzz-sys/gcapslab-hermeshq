import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from hermeshq.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,
    pool_size=30,       # Increased from 10 to handle concurrent WebSocket + API requests
    max_overflow=60,    # Increased from 20 to handle traffic spikes
    pool_timeout=30,
    pool_recycle=600,   # Reduced from 1800s to recycle stale connections faster
    pool_pre_ping=True, # Verify connections before use to avoid stale pool errors
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_database() -> None:
    """Run Alembic migrations to bring the database schema up to date.

    Uses subprocess to run Alembic, which avoids event-loop conflicts
    between Alembic's async env.py and the running FastAPI event loop.
    Fixed: uses 'head' (singular) instead of 'heads' to avoid issues
    with multiple migration heads.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    if result.returncode != 0:
        logger.error("Alembic migration failed:\n%s", result.stderr)
        raise RuntimeError(f"Alembic migration failed: {result.stderr}")
    logger.info("Alembic migrations applied successfully")
