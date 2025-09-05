"""
User API schemas for request/response validation.

This module provides Pydantic models for user-related API operations
with proper validation and security considerations.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from .common_schemas import ListResponse


class UserBase(BaseModel):
    """
    Base user schema with common fields.
    """
    email: EmailStr = Field(description="User email address")
    username: str = Field(
        min_length=3,
        max_length=50,
        description="Username"
    )
    full_name: str = Field(
        min_length=1,
        max_length=100,
        description="Full display name"
    )

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not v.isalnum() and '_' not in v and '-' not in v:
            raise ValueError(
                'Username must contain only alphanumeric characters, underscores, or hyphens')
        return v.lower()

    @validator('email')
    def validate_email(cls, v):
        """Normalize email to lowercase."""
        return v.lower()


class UserCreate(UserBase):
    """
    Schema for creating a new user.
    """
    role: Optional[str] = Field(
        default="user",
        description="User role"
    )


class UserUpdate(BaseModel):
    """
    Schema for updating user information.
    """
    email: Optional[EmailStr] = Field(
        default=None, description="New email address")
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="New username"
    )
    full_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="New full name"
    )

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if v is not None:
            if not v.isalnum() and '_' not in v and '-' not in v:
                raise ValueError(
                    'Username must contain only alphanumeric characters, underscores, or hyphens')
            return v.lower()
        return v

    @validator('email')
    def validate_email(cls, v):
        """Normalize email to lowercase."""
        if v is not None:
            return v.lower()
        return v


class UserResponse(UserBase):
    """
    Schema for user response data.
    """
    id: UUID = Field(description="User ID")
    role: str = Field(description="User role")
    is_active: bool = Field(description="Whether the user account is active")
    email_verified: bool = Field(description="Whether the email is verified")
    created_at: datetime = Field(description="Account creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    last_login_at: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp"
    )

    class Config:
        from_attributes = True


class UserListResponse(ListResponse):
    """
    Response schema for user list endpoints.
    """
    items: list[UserResponse] = Field(description="List of users")


class UserStatsResponse(BaseModel):
    """
    Response schema for user statistics.
    """
    user_id: str = Field(description="User ID")
    total_items: int = Field(description="Total number of items owned by user")
    is_active: bool = Field(description="Whether the user is active")
    email_verified: bool = Field(description="Whether email is verified")
    created_at: str = Field(description="Account creation timestamp")
    last_login_at: Optional[str] = Field(
        default=None,
        description="Last login timestamp"
    )
