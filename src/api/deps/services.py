"""
Service layer dependencies for FastAPI endpoints.

This module provides dependency injection for application services,
ensuring proper service lifecycle and database session management.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.services.user_service import UserService
from ...application.services.item_service import ItemService
from ...data.repositories.user_repository import UserRepository
from ...data.repositories.item_repository import ItemRepository
from .database import get_db


async def get_user_repository(
    db: AsyncSession = Depends(get_db)
) -> UserRepository:
    """
    FastAPI dependency to provide UserRepository instance.

    Creates and returns a UserRepository with proper database session.

    Args:
        db: Database session

    Returns:
        UserRepository: User repository instance
    """
    return UserRepository(db)


async def get_item_repository(
    db: AsyncSession = Depends(get_db)
) -> ItemRepository:
    """
    FastAPI dependency to provide ItemRepository instance.

    Creates and returns an ItemRepository with proper database session.

    Args:
        db: Database session

    Returns:
        ItemRepository: Item repository instance
    """
    return ItemRepository(db)


async def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository)
) -> UserService:
    """
    FastAPI dependency to provide UserService instance.

    Creates and returns a UserService with injected dependencies.

    Args:
        user_repository: User repository for data access

    Returns:
        UserService: User service instance with dependencies
    """
    return UserService(user_repository)


async def get_item_service(
    item_repository: ItemRepository = Depends(get_item_repository)
) -> ItemService:
    """
    FastAPI dependency to provide ItemService instance.

    Creates and returns an ItemService with injected dependencies.

    Args:
        item_repository: Item repository for data access

    Returns:
        ItemService: Item service instance with dependencies
    """
    return ItemService(item_repository)
