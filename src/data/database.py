"""
Database configuration and session management.

This module provides database connection setup, session management,
and dependency injection for FastAPI.
"""

import logging
from typing import AsyncGenerator, TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.pool import NullPool

from ..core.config import get_settings

if TYPE_CHECKING:
    from .repositories.user import UserRepository
    from .repositories.item import ItemRepository

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager for handling connections and sessions.
    """

    def __init__(self):
        """Initialize database manager."""
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self._settings = get_settings()

    @property
    def engine(self) -> AsyncEngine:
        """
        Get database engine.

        Returns:
            Async SQLAlchemy engine
        """
        if self._engine is None:
            self._engine = create_async_engine(
                self._settings.database_url,
                echo=self._settings.app_debug,
                future=True,
                poolclass=NullPool if self._settings.app_env == "test" else None,
                pool_pre_ping=True,
                pool_recycle=3600,  # 1 hour
                connect_args={
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "fastapi-backend",
                    }
                }
            )
        return self._engine

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """
        Get session maker.

        Returns:
            Async session maker
        """
        if self._sessionmaker is None:
            self._sessionmaker = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
        return self._sessionmaker

    async def create_session(self) -> AsyncSession:
        """
        Create a new database session.

        Returns:
            New async session
        """
        return self.sessionmaker()

    async def close(self):
        """
        Close database connections.
        """
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")

    async def health_check(self) -> bool:
        """
        Check database connectivity.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            from sqlalchemy import text
            async with self.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    This function provides database sessions with proper cleanup
    and can be used as a dependency in FastAPI route handlers.

    Yields:
        Database session
    """
    async with db_manager.sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """
    Get a database session for manual use.

    Note: This session needs to be manually closed.
    Use get_db() dependency for FastAPI routes.

    Returns:
        Database session
    """
    return await db_manager.create_session()


async def init_database():
    """
    Initialize database connections and perform startup checks.

    This function should be called during application startup.
    """
    try:
        # Test database connectivity
        health_check = await db_manager.health_check()
        if health_check:
            logger.info("Database connection established successfully")
        else:
            logger.error("Failed to establish database connection")
            raise Exception("Database connection failed")

        # Import models to ensure they are registered
        from .models import Base, User, Item  # noqa: F401

        logger.info("Database initialization completed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_database():
    """
    Close database connections during application shutdown.

    This function should be called during application shutdown.
    """
    await db_manager.close()


# Repository dependency functions
async def get_user_repository(
    session: AsyncSession = None
) -> "UserRepository":
    """
    Get UserRepository instance.

    Args:
        session: Optional database session

    Returns:
        UserRepository instance
    """
    from .repositories.user import UserRepository

    if session is None:
        session = await get_db_session()

    return UserRepository(session)


async def get_item_repository(
    session: AsyncSession = None
) -> "ItemRepository":
    """
    Get ItemRepository instance.

    Args:
        session: Optional database session

    Returns:
        ItemRepository instance
    """
    from .repositories.item import ItemRepository

    if session is None:
        session = await get_db_session()

    return ItemRepository(session)
