"""
User repository for user-specific database operations.

This module defines the UserRepository class that extends BaseRepository
with user-specific query methods.
"""

from typing import Dict, List, Optional
import uuid

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Repository class for User entities.

    Provides user-specific database operations extending the base
    CRUD functionality.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the user repository.

        Args:
            session: Async database session
        """
        super().__init__(User, session)

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username to search for

        Returns:
            User instance or None if not found
        """
        return await self.find_one_by_fields({'username': username})

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            email: Email address to search for

        Returns:
            User instance or None if not found
        """
        return await self.find_one_by_fields({'email': email})

    async def get_by_keycloak_sub(self, keycloak_sub: str) -> Optional[User]:
        """
        Get user by Keycloak subject ID.

        Args:
            keycloak_sub: Keycloak subject ID

        Returns:
            User instance or None if not found
        """
        return await self.find_one_by_fields({'keycloak_sub': keycloak_sub})

    async def find_by_username_or_email(
        self,
        identifier: str
    ) -> Optional[User]:
        """
        Find user by username or email.

        Args:
            identifier: Username or email to search for

        Returns:
            User instance or None if not found
        """
        query = select(self.model).where(
            or_(
                self.model.username == identifier,
                self.model.email == identifier
            )
        )

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def search_users(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Search users by username, email, first name, or last name.

        Args:
            search_term: Term to search for
            skip: Number of users to skip
            limit: Maximum number of users to return

        Returns:
            List of matching users
        """
        search_pattern = f"%{search_term.lower()}%"

        query = select(self.model).where(
            or_(
                func.lower(self.model.username).like(search_pattern),
                func.lower(self.model.email).like(search_pattern),
                func.lower(self.model.first_name).like(search_pattern),
                func.lower(self.model.last_name).like(search_pattern)
            )
        )

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        query = query.order_by(self.model.username).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Get active (non-deleted, non-suspended) users.

        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return

        Returns:
            List of active users
        """
        filters = {'is_active': True}
        return await self.find_by_fields(
            filters=filters,
            skip=skip,
            limit=limit,
            order_by='username'
        )

    async def get_users_by_role(
        self,
        role: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Get users by role.

        Args:
            role: Role to filter by
            skip: Number of users to skip
            limit: Maximum number of users to return

        Returns:
            List of users with the specified role
        """
        query = select(self.model).where(
            self.model.roles.op('@>')([role])
        )

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        query = query.order_by(self.model.username).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_users_with_items(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Get users with their items loaded.

        Args:
            skip: Number of users to skip
            limit: Maximum number of users to return

        Returns:
            List of users with items relationship loaded
        """
        query = (
            select(self.model)
            .options(selectinload(self.model.items))
            .where(self.model.deleted_at.is_(None))
            .order_by(self.model.username)
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self, is_active: bool = True) -> int:
        """
        Count users by active status.

        Args:
            is_active: Whether to count active or inactive users

        Returns:
            Count of users with specified status
        """
        query = select(func.count(self.model.id)).where(
            and_(
                self.model.is_active == is_active,
                self.model.deleted_at.is_(None)
            )
        )

        result = await self.session.execute(query)
        return result.scalar()

    async def update_last_login(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Update user's last login timestamp.

        Args:
            user_id: User ID

        Returns:
            Updated user instance or None if not found
        """
        return await self.update(user_id, {'last_login_at': func.now()})

    async def update_preferences(
        self,
        user_id: uuid.UUID,
        preferences: Dict
    ) -> Optional[User]:
        """
        Update user preferences.

        Args:
            user_id: User ID
            preferences: New preferences dictionary

        Returns:
            Updated user instance or None if not found
        """
        return await self.update(user_id, {'preferences': preferences})

    async def add_role(self, user_id: uuid.UUID, role: str) -> Optional[User]:
        """
        Add role to user.

        Args:
            user_id: User ID
            role: Role to add

        Returns:
            Updated user instance or None if not found
        """
        user = await self.get_by_id(user_id)
        if user:
            if not user.roles:
                user.roles = []
            if role not in user.roles:
                user.roles.append(role)
                await self.session.flush()
                await self.session.refresh(user)
        return user

    async def remove_role(self, user_id: uuid.UUID, role: str) -> Optional[User]:
        """
        Remove role from user.

        Args:
            user_id: User ID
            role: Role to remove

        Returns:
            Updated user instance or None if not found
        """
        user = await self.get_by_id(user_id)
        if user and user.roles and role in user.roles:
            user.roles.remove(role)
            await self.session.flush()
            await self.session.refresh(user)
        return user

    async def verify_unique_username(
        self,
        username: str,
        exclude_user_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Verify that username is unique.

        Args:
            username: Username to check
            exclude_user_id: User ID to exclude from check (for updates)

        Returns:
            True if username is unique, False otherwise
        """
        query = select(self.model.id).where(self.model.username == username)

        if exclude_user_id:
            query = query.where(self.model.id != exclude_user_id)

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is None

    async def verify_unique_email(
        self,
        email: str,
        exclude_user_id: Optional[uuid.UUID] = None
    ) -> bool:
        """
        Verify that email is unique.

        Args:
            email: Email to check
            exclude_user_id: User ID to exclude from check (for updates)

        Returns:
            True if email is unique, False otherwise
        """
        query = select(self.model.id).where(self.model.email == email)

        if exclude_user_id:
            query = query.where(self.model.id != exclude_user_id)

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is None
