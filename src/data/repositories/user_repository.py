"""
User repository implementation with security features.

This module provides secure user data access operations with built-in
IDOR protection and search capabilities.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User, dict, dict]):
    """
    Repository for User model operations.

    Provides secure CRUD operations and user-specific queries
    with built-in protection against common vulnerabilities.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize user repository.

        Args:
            session: Async database session
        """
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: Email address to search for

        Returns:
            User instance or None if not found
        """
        stmt = select(self.model).where(
            and_(
                self.model.email == email.lower(),
                self.model.deleted_at.is_(None)  # Exclude soft-deleted users
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_keycloak_id(self, keycloak_id: str) -> Optional[User]:
        """
        Get user by Keycloak subject ID.

        Args:
            keycloak_id: Keycloak subject ID (from JWT 'sub' claim)

        Returns:
            User instance or None if not found
        """
        stmt = select(self.model).where(
            and_(
                self.model.keycloak_id == keycloak_id,
                self.model.deleted_at.is_(None)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(self, query: str, owner_id: Optional[UUID] = None) -> List[User]:
        """
        Search users by name, username, or email.

        Args:
            query: Search query string
            owner_id: Not used for user search (users don't have owners)

        Returns:
            List of matching users
        """
        search_term = f"%{query.lower()}%"

        stmt = select(self.model).where(
            and_(
                or_(
                    self.model.full_name.ilike(search_term),
                    self.model.username.ilike(search_term),
                    self.model.email.ilike(search_term)
                ),
                self.model.deleted_at.is_(None),
                self.model.is_active == True  # Only return active users
            )
        ).limit(50)  # Limit search results

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def email_exists(self, email: str, exclude_user_id: Optional[UUID] = None) -> bool:
        """
        Check if email already exists in the system.

        Args:
            email: Email address to check
            exclude_user_id: Optional user ID to exclude from check (for updates)

        Returns:
            True if email exists, False otherwise
        """
        stmt = select(self.model.id).where(
            and_(
                self.model.email == email.lower(),
                self.model.deleted_at.is_(None)
            )
        )

        if exclude_user_id:
            stmt = stmt.where(self.model.id != exclude_user_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
