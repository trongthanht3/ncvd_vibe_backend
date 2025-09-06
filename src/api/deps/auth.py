"""
Authentication dependencies for FastAPI endpoints.

This module provides authentication and authorization dependencies
with proper JWT validation and user context injection, prioritizing local JWT tokens over Keycloak.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user as core_get_current_user, get_current_active_user as core_get_current_active_user, TokenData
from ...application.services.user_service import UserService
from ...api.schemas.user_schemas import UserResponse
from ...core.exceptions import UnauthorizedError, NotFoundError
from .database import get_db
from .services import get_user_service

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    FastAPI dependency to get the current authenticated user.

    Validates JWT token (prioritizing local tokens over Keycloak) and returns user information 
    with proper error handling for authentication failures.

    Args:
        credentials: HTTP Bearer credentials from request
        user_service: User service for user operations
        db: Database session

    Returns:
        UserResponse: Current user information

    Raises:
        HTTPException: If authentication fails or user not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Use core authentication that prioritizes local JWT tokens
        token_data: TokenData = await core_get_current_user(credentials)

        # Try to get user from database using user_id first (local auth)
        if token_data.user_id:
            try:
                user_uuid = UUID(token_data.user_id)
                # For authentication purposes, allow user to access their own data
                user = await user_service.get_user_by_id(
                    user_uuid,
                    requesting_user_id=user_uuid,
                    requesting_user_role="user"
                )
                if user and user.is_active:
                    return user
            except (ValueError, Exception):
                # Invalid UUID or other error, fall back to keycloak lookup
                pass

        # Fallback to Keycloak user lookup if local lookup failed
        user = await user_service.get_user_by_keycloak_id(token_data.user_id)
        if not user:
            raise NotFoundError("User not found")

        return user

    except (UnauthorizedError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service),
    db: AsyncSession = Depends(get_db)
) -> Optional[UserResponse]:
    """
    FastAPI dependency to optionally get the current authenticated user.

    Similar to get_current_user but returns None instead of raising
    an exception when authentication fails. Useful for endpoints
    that work for both authenticated and anonymous users.

    Args:
        credentials: HTTP Bearer credentials from request
        user_service: User service for user operations
        db: Database session

    Returns:
        UserResponse or None: Current user information or None if not authenticated
    """
    if not credentials:
        return None

    try:
        # Use core authentication that prioritizes local JWT tokens
        token_data: TokenData = await core_get_current_user(credentials)

        # Try to get user from database using user_id first (local auth)
        if token_data.user_id:
            try:
                user_uuid = UUID(token_data.user_id)
                # For authentication purposes, allow user to access their own data
                user = await user_service.get_user_by_id(
                    user_uuid,
                    requesting_user_id=user_uuid,
                    requesting_user_role="user"
                )
                if user and user.is_active:
                    return user
            except (ValueError, Exception):
                # Invalid UUID or other error, fall back to keycloak lookup
                pass

        # Fallback to Keycloak user lookup
        user = await user_service.get_user_by_keycloak_id(token_data.user_id)
        return user

    except Exception:
        # Silently return None for any authentication errors
        return None


def require_role(required_role: str):
    """
    Dependency factory for role-based access control.

    Creates a dependency that validates the user has the required role.

    Args:
        required_role: Role required to access the endpoint

    Returns:
        Dependency function that validates user role
    """
    async def check_role(
        current_user: UserResponse = Depends(get_current_user)
    ) -> UserResponse:
        """
        Check if current user has the required role.

        Args:
            current_user: Current authenticated user

        Returns:
            UserResponse: Current user if role check passes

        Raises:
            HTTPException: If user doesn't have required role
        """
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}"
            )
        return current_user

    return check_role


def require_admin():
    """
    Dependency that requires admin role.

    Returns:
        Dependency function that validates admin role
    """
    return require_role("admin")


async def get_current_user_id(
    current_user: UserResponse = Depends(get_current_user)
) -> UUID:
    """
    FastAPI dependency to get just the current user's ID.

    Convenient dependency for endpoints that only need the user ID
    rather than the full user object.

    Args:
        current_user: Current authenticated user

    Returns:
        UUID: Current user's ID
    """
    return current_user.id


async def get_current_user_role(
    current_user: UserResponse = Depends(get_current_user)
) -> str:
    """
    FastAPI dependency to get just the current user's role.

    Convenient dependency for endpoints that only need the user role
    for authorization decisions.

    Args:
        current_user: Current authenticated user

    Returns:
        str: Current user's role
    """
    return current_user.role
