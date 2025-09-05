"""
Base model and database utilities.

This module provides the SQLAlchemy base class and common database utilities
for all models in the application.
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Provides common fields and functionality for all database models.
    """

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Generate table name automatically from class name.

        Returns:
            Snake_case table name derived from class name
        """
        # Convert CamelCase to snake_case
        name = cls.__name__
        result = ""
        for i, char in enumerate(name):
            if i > 0 and char.isupper():
                result += "_"
            result += char.lower()
        return result

    # Primary key using UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Primary key UUID"
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Record creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Record last update timestamp"
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Returns:
            Dictionary representation of the model
        """
        return {
            column.key: getattr(self, column.key)
            for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """
        String representation of the model.

        Returns:
            String representation showing class name and ID
        """
        return f"<{self.__class__.__name__}(id={self.id})>"


class TimestampMixin:
    """
    Mixin class for models that need custom timestamp fields.

    Provides created_at and updated_at fields that can be customized
    beyond the default Base implementation.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Record creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Record last update timestamp"
    )


class SoftDeleteMixin:
    """
    Mixin class for models that support soft deletion.

    Adds a deleted_at field that indicates when a record was soft deleted.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Record soft deletion timestamp"
    )

    @property
    def is_deleted(self) -> bool:
        """
        Check if the record is soft deleted.

        Returns:
            True if the record is soft deleted, False otherwise
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """
        Mark the record as soft deleted.

        Sets the deleted_at timestamp to the current time.
        """
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """
        Restore a soft deleted record.

        Sets the deleted_at field to None.
        """
        self.deleted_at = None
