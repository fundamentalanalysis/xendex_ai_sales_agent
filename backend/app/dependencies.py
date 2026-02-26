"""Application dependencies and database initialization."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import structlog

from app.config import settings
from app.models.base import Base

logger = structlog.get_logger()

# Create async engine with restricted pool for cloud limits
# Aiven free tier has very low connection limits - keep pool minimal
engine = create_async_engine(
    settings.get_database_url,
    echo=settings.debug,
    future=True,
    pool_size=1,          # Minimal pool size for Aiven (limit ~5 connections total)
    max_overflow=4,       # Allow burst connections up to 5 total
    pool_recycle=300,     # Recycle frequently
    pool_pre_ping=True,
    pool_timeout=30,
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


from tenacity import retry, stop_after_attempt, wait_fixed, before_sleep_log
import logging

@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(2),
    before_sleep=before_sleep_log(logger, logging.INFO)
)
async def init_db() -> None:
    """Initialize database tables with retry logic."""
    logger.info(f"Connecting to database at {settings.get_database_url.split('@')[-1]}")  # Log host only for safety
    async with engine.begin() as conn:
        # In production, use Alembic migrations instead
        # For now, we create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
