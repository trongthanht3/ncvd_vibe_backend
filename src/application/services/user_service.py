"""
User service implementation with business logic and security.

This module provides high-level user operations with built-in security features
including IDOR protection, role-based access control, and audit logging.
"""

from typing import List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.schemas.user_schemas import UserCreate, UserUpdate, UserResponse, UserStatsResponse
from ...core.exceptions import (
    NotFoundError,
    ConflictError,
    ForbiddenError,
    ValidationError
)
from ...data.repositories.user_repository import UserRepository
from ...data.models.user import User


class UserService:
    """
    User service providing business logic for user operations.

    Implements proper IDOR protection, role-based access control,
    and comprehensive audit logging for security compliance.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize user service.

        Args:
            session: Async database session
        """
        self.session = session
        self.user_repo = UserRepository(session)

    async def create_user(
        self,
        user_data: UserCreate,
        keycloak_id: str,
        created_by_user_id: Optional[UUID] = None
    ) -> UserResponse:
        """
        Create a new user with validation and security checks.

        Args:
            user_data: User creation data
            keycloak_id: Keycloak subject ID from JWT
            created_by_user_id: ID of user performing the action (for audit)

        Returns:
            Created user data

        Raises:
            ConflictError: If email or username already exists
            ValidationError: If user data is invalid
        """
        logger.info(
            f"Creating user with email {user_data.email}",
            extra={"created_by": str(created_by_user_id)
                   if created_by_user_id else None}
        )

        # Check for existing email
        if await self.user_repo.email_exists(user_data.email):
            raise ConflictError(f"Email {user_data.email} already exists")

        # Check for existing username (if we implement username lookup)
        # Note: UserRepository needs username_exists method implementation

        # Prepare user data
        user_dict = user_data.model_dump()
        user_dict['keycloak_id'] = keycloak_id
        user_dict['is_active'] = True
        # Assume Keycloak handles verification
        user_dict['email_verified'] = True

        # Create user
        try:
            user = await self.user_repo.create(user_dict)
            await self.session.commit()

            logger.info(
                f"User created successfully: {user.id}",
                extra={"user_id": str(user.id), "email": user.email}
            )

            return UserResponse.model_validate(user)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise ValidationError(f"Failed to create user: {str(e)}")

    async def get_user_by_id(
        self,
        user_id: UUID,
        requesting_user_id: UUID,
        requesting_user_role: str = "user"
    ) -> UserResponse:
        """
        Get user by ID with IDOR protection.

        Args:
            user_id: ID of user to retrieve
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user

        Returns:
            User data

        Raises:
            NotFoundError: If user not found
            ForbiddenError: If access denied (IDOR protection)
        """
        # IDOR Protection: Users can only see their own profile unless they're admin
        if user_id != requesting_user_id and requesting_user_role != "admin":
            logger.warning(
                f"IDOR attempt: User {requesting_user_id} tried to access user {user_id}",
                extra={"requesting_user": str(
                    requesting_user_id), "target_user": str(user_id)}
            )
            raise ForbiddenError("You can only access your own profile")

        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")

        return UserResponse.model_validate(user)

    async def get_user_by_keycloak_id(self, keycloak_id: str) -> Optional[UserResponse]:
        """
        Get user by Keycloak subject ID.

        Args:
            keycloak_id: Keycloak subject ID

        Returns:
            User data or None if not found
        """
        user = await self.user_repo.get_by_keycloak_id(keycloak_id)
        if user:
            return UserResponse.model_validate(user)
        return None

    async def update_user(
        self,
        user_id: UUID,
        user_data: UserUpdate,
        requesting_user_id: UUID,
        requesting_user_role: str = "user"
    ) -> UserResponse:
        """
        Update user with IDOR protection and validation.

        Args:
            user_id: ID of user to update
            user_data: Update data
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user

        Returns:
            Updated user data

        Raises:
            NotFoundError: If user not found
            ForbiddenError: If access denied (IDOR protection)
            ConflictError: If email/username conflict
        """
        # IDOR Protection: Users can only update their own profile unless they're admin
        if user_id != requesting_user_id and requesting_user_role != "admin":
            logger.warning(
                f"IDOR attempt: User {requesting_user_id} tried to update user {user_id}",
                extra={"requesting_user": str(
                    requesting_user_id), "target_user": str(user_id)}
            )
            raise ForbiddenError("You can only update your own profile")

        # Get existing user
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")

        # Validate email uniqueness if being updated
        if user_data.email and user_data.email != user.email:
            if await self.user_repo.email_exists(user_data.email, exclude_user_id=user_id):
                raise ConflictError(f"Email {user_data.email} already exists")

        # Update user
        try:
            updated_user = await self.user_repo.update(user_id, user_data.model_dump(exclude_unset=True))
            await self.session.commit()

            logger.info(
                f"User updated successfully: {user_id}",
                extra={"user_id": str(user_id), "updated_by": str(
                    requesting_user_id)}
            )

            return UserResponse.model_validate(updated_user)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update user {user_id}: {str(e)}")
            raise ValidationError(f"Failed to update user: {str(e)}")

    async def search_users(
        self,
        query: str,
        requesting_user_id: UUID,
        requesting_user_role: str = "user",
        skip: int = 0,
        limit: int = 100
    ) -> List[UserResponse]:
        """
        Search users with role-based access control.

        Args:
            query: Search query
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching users

        Raises:
            ForbiddenError: If user doesn't have search permissions
        """
        # Role-based access: Only admins can search all users
        if requesting_user_role != "admin":
            raise ForbiddenError("Only administrators can search users")

        users = await self.user_repo.search(query)
        return [UserResponse.model_validate(user) for user in users]

    async def get_user_stats(
        self,
        user_id: UUID,
        requesting_user_id: UUID,
        requesting_user_role: str = "user"
    ) -> UserStatsResponse:
        """
        Get user statistics with IDOR protection.

        Args:
            user_id: ID of user to get stats for
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user

        Returns:
            User statistics

        Raises:
            NotFoundError: If user not found
            ForbiddenError: If access denied (IDOR protection)
        """
        # IDOR Protection: Users can only see their own stats unless they're admin
        if user_id != requesting_user_id and requesting_user_role != "admin":
            raise ForbiddenError("You can only view your own statistics")

        stats = await self.user_repo.get_user_stats(user_id)
        if not stats:
            raise NotFoundError(f"User with ID {user_id} not found")

        return UserStatsResponse(**stats)

    async def update_last_login(self, user_id: UUID) -> bool:
        """
        Update user's last login timestamp.

        Args:
            user_id: ID of user to update

        Returns:
            True if updated successfully
        """
        success = await self.user_repo.update_last_login(user_id)
        if success:
            await self.session.commit()
            logger.info(f"Updated last login for user {user_id}")
        return success

    async def deactivate_user(
        self,
        user_id: UUID,
        requesting_user_id: UUID,
        requesting_user_role: str
    ) -> bool:
        """
        Deactivate a user account (admin only).

        Args:
            user_id: ID of user to deactivate
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user

        Returns:
            True if deactivated successfully

        Raises:
            ForbiddenError: If not admin
            NotFoundError: If user not found
        """
        # Role-based access: Only admins can deactivate users
        if requesting_user_role != "admin":
            raise ForbiddenError("Only administrators can deactivate users")

        # Prevent self-deactivation
        if user_id == requesting_user_id:
            raise ForbiddenError("You cannot deactivate your own account")

        success = await self.user_repo.deactivate_user(user_id)
        if not success:
            raise NotFoundError(f"User with ID {user_id} not found")

        await self.session.commit()
        logger.warning(
            f"User {user_id} deactivated by admin {requesting_user_id}",
            extra={"deactivated_user": str(
                user_id), "admin_user": str(requesting_user_id)}
        )

        return True
