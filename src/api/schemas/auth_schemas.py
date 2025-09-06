"""
Authentication API schemas for request/response validation.

This module provides Pydantic models for authentication-related API operations
including login, registration, and token management.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from .user_schemas import UserResponse


class LoginRequest(BaseModel):
    """
    Schema for user login request.
    """
    username: str = Field(
        min_length=3,
        max_length=50,
        description="Username or email address"
    )
    password: str = Field(
        min_length=6,
        max_length=128,
        description="User password"
    )

    @validator('username')
    def validate_username(cls, v):
        """Normalize username to lowercase."""
        return v.lower().strip()


class RegisterRequest(BaseModel):
    """
    Schema for user registration request.
    """
    username: str = Field(
        min_length=3,
        max_length=50,
        description="Username"
    )
    email: EmailStr = Field(description="Email address")
    password: str = Field(
        min_length=6,
        max_length=128,
        description="User password"
    )
    first_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="First name"
    )
    last_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Last name"
    )

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(
                'Username must contain only alphanumeric characters, underscores, or hyphens')
        return v.lower().strip()

    @validator('email')
    def validate_email(cls, v):
        """Normalize email to lowercase."""
        return v.lower().strip()

    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError(
                'Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError(
                'Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class TokenResponse(BaseModel):
    """
    Schema for authentication token response.
    """
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")
    refresh_token: Optional[str] = Field(
        default=None,
        description="JWT refresh token"
    )


class AuthResponse(BaseModel):
    """
    Schema for authentication response including user data.
    """
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")
    refresh_token: Optional[str] = Field(
        default=None,
        description="JWT refresh token"
    )
    user: UserResponse = Field(description="Authenticated user information")


class RefreshTokenRequest(BaseModel):
    """
    Schema for token refresh request.
    """
    refresh_token: str = Field(description="JWT refresh token")


class ChangePasswordRequest(BaseModel):
    """
    Schema for password change request.
    """
    current_password: str = Field(description="Current password")
    new_password: str = Field(
        min_length=6,
        max_length=128,
        description="New password"
    )

    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength."""
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError(
                'Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError(
                'Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class LogoutResponse(BaseModel):
    """
    Schema for logout response.
    """
    message: str = Field(default="Successfully logged out",
                         description="Logout message")
    logged_out_at: datetime = Field(description="Logout timestamp")
