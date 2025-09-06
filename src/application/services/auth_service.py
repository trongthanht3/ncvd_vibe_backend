"""
Authentication service for handling user authentication operations.

This service provides methods for user registration, login, password management,
and token operations for local username/password authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from ...data.models.user import User
from ...core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_access_token,
    SecurityError
)
from ...core.logging import get_logger
from ...api.schemas.auth_schemas import (
    LoginRequest,
    RegisterRequest,
    AuthResponse,
    TokenResponse,
    ChangePasswordRequest
)
from ...api.schemas.user_schemas import UserResponse

logger = get_logger(__name__)


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the authentication service.

        Args:
            db: Database session
        """
        self.db = db

    async def register_user(self, request: RegisterRequest) -> UserResponse:
        """
        Register a new user with username/password authentication.

        Args:
            request: User registration data

        Returns:
            UserResponse: Created user information

        Raises:
            HTTPException: If registration fails
        """
        try:
            # Check if user already exists
            existing_user = await self._get_user_by_email_or_username(
                request.email, request.username
            )
            if existing_user:
                if existing_user.email == request.email:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User with this email already exists"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="User with this username already exists"
                    )

            # Create new user
            user = User(
                username=request.username,
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
                is_active=True,
                is_verified=False,  # Can implement email verification later
                keycloak_sub=None,  # This is a direct auth user
            )

            # Set password
            user.set_password(request.password)

            # Save user
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            logger.info(f"User registered successfully: {user.email}")

            return self._user_to_response(user)

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error registering user {request.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register user"
            )

    async def login_user(self, request: LoginRequest) -> AuthResponse:
        """
        Authenticate user with username/password and return tokens.

        Args:
            request: Login credentials

        Returns:
            AuthResponse: Authentication tokens and user information

        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Find user by username or email
            user = await self._get_user_by_email_or_username(
                request.username, request.username
            )

            if not user:
                # Don't reveal whether user exists or not
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )

            # Check if account is locked
            if user.is_account_locked:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account is temporarily locked due to failed login attempts"
                )

            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is disabled"
                )

            # Verify password
            if not user.verify_password(request.password):
                # Record failed login attempt
                user.record_failed_login()
                self.db.add(user)  # Ensure user is tracked in session
                await self.db.commit()

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )

            # Authentication successful - reset failed attempts
            user.record_successful_login()
            self.db.add(user)  # Ensure user is tracked in session
            await self.db.commit()

            # Generate tokens
            access_token, expires_in = self._create_access_token_for_user(user)
            refresh_token = self._create_refresh_token_for_user(user)

            logger.info(f"User logged in successfully: {user.email}")

            return AuthResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=expires_in,
                refresh_token=refresh_token,
                user=self._user_to_response(user)
            )

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error during login for {request.username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed"
            )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: JWT refresh token

        Returns:
            TokenResponse: New access token

        Raises:
            HTTPException: If refresh fails
        """
        try:
            # Verify refresh token
            payload = verify_access_token(refresh_token)

            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )

            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )

            # Get user
            user = await self._get_user_by_id(UUID(user_id))
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )

            # Generate new access token
            access_token, expires_in = self._create_access_token_for_user(user)

            logger.info(f"Token refreshed for user: {user.email}")

            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=expires_in
            )

        except SecurityError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed"
            )

    async def change_password(
        self,
        user_id: UUID,
        request: ChangePasswordRequest
    ) -> Dict[str, str]:
        """
        Change user's password.

        Args:
            user_id: User ID
            request: Password change data

        Returns:
            Success message

        Raises:
            HTTPException: If password change fails
        """
        try:
            # Get user
            user = await self._get_user_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Verify current password
            if not user.verify_password(request.current_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )

            # Set new password
            user.set_password(request.new_password)
            await self.db.commit()

            logger.info(f"Password changed for user: {user.email}")

            return {"message": "Password changed successfully"}

        except HTTPException:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error changing password for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )

    def _create_access_token_for_user(self, user: User) -> Tuple[str, int]:
        """
        Create access token for user.

        Args:
            user: User object

        Returns:
            Tuple of (token, expires_in_seconds)
        """
        expires_delta = timedelta(hours=24)  # 24 hour expiration

        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "roles": ["user"],  # Default role, can be extended
            "type": "access"
        }

        token = create_access_token(token_data, expires_delta)
        return token, int(expires_delta.total_seconds())

    def _create_refresh_token_for_user(self, user: User) -> str:
        """
        Create refresh token for user.

        Args:
            user: User object

        Returns:
            JWT refresh token
        """
        return create_refresh_token(str(user.id))

    async def _get_user_by_email_or_username(
        self,
        email: str,
        username: str
    ) -> Optional[User]:
        """
        Get user by email or username.

        Args:
            email: Email address
            username: Username

        Returns:
            User object if found, None otherwise
        """
        stmt = select(User).where(
            (User.email == email.lower()) | (User.username == username.lower())
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User object if found, None otherwise
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _user_to_response(self, user: User) -> UserResponse:
        """
        Convert User model to UserResponse.

        Args:
            user: User model

        Returns:
            UserResponse
        """
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role="user",  # Default role
            is_active=user.is_active,
            email_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login
        )
