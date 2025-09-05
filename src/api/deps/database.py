"""
Database dependency for FastAPI dependency injection.

This module provides database session dependencies for API endpoints
with proper connection lifecycle management.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ...data.database import get_db as get_database_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session injection.

    Provides an async database session with automatic connection
    lifecycle management and transaction handling.

    Yields:
        AsyncSession: Database session
    """
    async for session in get_database_session():
        yield session
