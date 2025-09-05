"""
User model for authentication and authorization.

This module defines the User model that represents users in the system.
User authentication is handled by Keycloak, but we store user metadata locally.
"""

from typing import List, Optional

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin

# Forward reference for Item model to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .item import Item


class User(Base, SoftDeleteMixin):
    """
    User model representing system users.

    This model stores user metadata and profile information.
    Authentication is handled by Keycloak, and the 'sub' field
    corresponds to the Keycloak user ID.
    """

    # Keycloak subject identifier (unique across all realms)
    keycloak_sub: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="Keycloak subject identifier"
    )

    # User profile information
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        doc="Username (should match Keycloak username)"
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="User email address"
    )

    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="User first name"
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="User last name"
    )

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the user account is active"
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the user email is verified"
    )

    # Additional profile information
    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="URL to user's profile picture"
    )

    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="User biography/description"
    )

    # Preferences and metadata stored as JSON
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="User preferences stored as JSON"
    )

    user_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional user metadata stored as JSON"
    )

    # Relationships
    items: Mapped[list["Item"]] = relationship(
        "Item",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        """
        String representation of the user.

        Returns:
            String representation showing username and email
        """
        return f"<User(username='{self.username}', email='{self.email}')>"

    @property
    def full_name(self) -> str:
        """
        Get the user's full name.

        Returns:
            Full name combining first and last name, or username if names are not available
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username

    @property
    def display_name(self) -> str:
        """
        Get a suitable display name for the user.

        Returns:
            Display name (full name if available, otherwise username)
        """
        if self.first_name or self.last_name:
            return self.full_name
        return self.username

    def update_profile(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture_url: Optional[str] = None,
    ) -> None:
        """
        Update user profile information.

        Args:
            first_name: Updated first name
            last_name: Updated last name
            bio: Updated biography
            profile_picture_url: Updated profile picture URL
        """
        if first_name is not None:
            self.first_name = first_name
        if last_name is not None:
            self.last_name = last_name
        if bio is not None:
            self.bio = bio
        if profile_picture_url is not None:
            self.profile_picture_url = profile_picture_url

    def update_preferences(self, preferences: dict) -> None:
        """
        Update user preferences.

        Args:
            preferences: Dictionary of user preferences
        """
        if self.preferences is None:
            self.preferences = {}
        self.preferences.update(preferences)

    def update_metadata(self, metadata: dict) -> None:
        """
        Update user metadata.

        Args:
            metadata: Dictionary of user metadata
        """
        if self.user_metadata is None:
            self.user_metadata = {}
        self.user_metadata.update(metadata)


# Create database indexes
Index('idx_user_keycloak_sub', User.keycloak_sub)
Index('idx_user_username', User.username)
Index('idx_user_email', User.email)
Index('idx_user_active', User.is_active)
Index('idx_user_deleted', User.deleted_at)
