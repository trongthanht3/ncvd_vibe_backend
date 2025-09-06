"""
User model for authentication and authorization.

This module defines the User model that represents users in the system.
User authentication is handled by Keycloak, but we store user metadata locally.
"""

from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy import Boolean, Index, String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base, SoftDeleteMixin

# Forward reference for Item model to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .item import Item
    from .document import Document


class User(Base, SoftDeleteMixin):
    """
    User model representing system users.

    This model stores user metadata and profile information.
    Authentication is handled by Keycloak, and the 'sub' field
    corresponds to the Keycloak user ID.
    """

    # Keycloak subject identifier (unique across all realms)
    # Made optional to support both Keycloak and direct authentication
    keycloak_sub: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        doc="Keycloak subject identifier (optional for direct auth users)"
    )

    # Password fields for direct authentication
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Hashed password for direct authentication"
    )

    # Authentication metadata
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of last successful login"
    )

    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of consecutive failed login attempts"
    )

    account_locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Account lock expiration time"
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

    documents: Mapped[list["Document"]] = relationship(
        "Document",
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

    @property
    def is_keycloak_user(self) -> bool:
        """
        Check if this is a Keycloak-authenticated user.

        Returns:
            True if user authenticates via Keycloak, False for direct auth
        """
        return self.keycloak_sub is not None

    @property
    def is_direct_auth_user(self) -> bool:
        """
        Check if this is a direct-authentication user.

        Returns:
            True if user authenticates directly (has password), False for Keycloak
        """
        return self.password_hash is not None

    @property
    def is_account_locked(self) -> bool:
        """
        Check if the account is currently locked.

        Returns:
            True if account is locked, False otherwise
        """
        if self.account_locked_until is None:
            return False
        return datetime.utcnow() < self.account_locked_until

    def set_password(self, password: str) -> None:
        """
        Set the user's password (hash it).

        Args:
            password: Plain text password to hash and store
        """
        from ...core.security import hash_password
        self.password_hash = hash_password(password)

    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        if not self.password_hash:
            return False

        from ...core.security import verify_password
        return verify_password(password, self.password_hash)

    def record_failed_login(self) -> None:
        """
        Record a failed login attempt and lock account if necessary.
        """
        self.failed_login_attempts += 1

        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=30)

    def record_successful_login(self) -> None:
        """
        Record a successful login and reset failed attempts.
        """
        self.last_login = datetime.utcnow()
        self.failed_login_attempts = 0
        self.account_locked_until = None


# Create database indexes
Index('idx_user_keycloak_sub', User.keycloak_sub)
Index('idx_user_username', User.username)
Index('idx_user_email', User.email)
Index('idx_user_active', User.is_active)
Index('idx_user_deleted', User.deleted_at)
