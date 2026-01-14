"""Database engine and session configuration."""

from collections.abc import AsyncGenerator

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(create_tables: bool = False) -> None:
    """Initialize database connection and optionally create tables.

    Args:
        create_tables: If True, auto-create tables (for development).
                      In production, use Alembic migrations instead.
    """
    from app.db import models  # noqa: F401

    if create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        # Just verify connection works
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        logger.info("database_connection_verified")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("database_connections_closed")
