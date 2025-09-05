"""
Item model for application data.

This module defines the Item model that represents the main data entities
in the system. Items can have vector embeddings stored in Milvus.
"""

from typing import Optional
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin

# Forward reference for User model to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User


class Item(Base, SoftDeleteMixin):
    """
    Item model representing main data entities.

    Items can have associated vector embeddings stored in Milvus
    for similarity search functionality.
    """

    # Basic item information
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Item title"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Item description"
    )

    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Main item content"
    )

    # Owner relationship
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the user who owns this item"
    )

    # Status and visibility
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the item is publicly visible"
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the item is featured"
    )

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Item category"
    )

    tags: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Item tags stored as JSON array"
    )

    # Vector embedding information
    has_embedding: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the item has a vector embedding"
    )

    milvus_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        doc="Milvus vector ID for this item"
    )

    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Name of the embedding model used"
    )

    embedding_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Version of the embedding model"
    )

    # Metrics and analytics
    view_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        doc="Number of times this item has been viewed"
    )

    like_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        doc="Number of likes this item has received"
    )

    similarity_threshold: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Similarity threshold for vector searches"
    )

    # Additional metadata
    item_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional item metadata stored as JSON"
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="items",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """
        String representation of the item.

        Returns:
            String representation showing title and owner
        """
        return f"<Item(title='{self.title}', owner_id={self.owner_id})>"

    @property
    def display_title(self) -> str:
        """
        Get a display-friendly title.

        Returns:
            Item title, truncated if necessary
        """
        if len(self.title) > 50:
            return f"{self.title[:47]}..."
        return self.title

    def increment_view_count(self) -> None:
        """
        Increment the view count for this item.
        """
        self.view_count += 1

    def increment_like_count(self) -> None:
        """
        Increment the like count for this item.
        """
        self.like_count += 1

    def decrement_like_count(self) -> None:
        """
        Decrement the like count for this item.

        Ensures the count doesn't go below zero.
        """
        if self.like_count > 0:
            self.like_count -= 1

    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the item.

        Args:
            tag: Tag to add
        """
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from the item.

        Args:
            tag: Tag to remove
        """
        if self.tags and tag in self.tags:
            self.tags.remove(tag)

    def update_metadata(self, metadata: dict) -> None:
        """
        Update item metadata.

        Args:
            metadata: Dictionary of metadata to update
        """
        if self.item_metadata is None:
            self.item_metadata = {}
        self.item_metadata.update(metadata)

    def set_embedding_info(
        self,
        milvus_id: str,
        model: str,
        version: str
    ) -> None:
        """
        Set embedding information for the item.

        Args:
            milvus_id: Milvus vector ID
            model: Embedding model name
            version: Embedding model version
        """
        self.milvus_id = milvus_id
        self.embedding_model = model
        self.embedding_version = version
        self.has_embedding = True

    def clear_embedding_info(self) -> None:
        """
        Clear embedding information for the item.
        """
        self.milvus_id = None
        self.embedding_model = None
        self.embedding_version = None
        self.has_embedding = False


# Create database indexes
Index('idx_item_title', Item.title)
Index('idx_item_owner_id', Item.owner_id)
Index('idx_item_category', Item.category)
Index('idx_item_public', Item.is_public)
Index('idx_item_featured', Item.is_featured)
Index('idx_item_has_embedding', Item.has_embedding)
Index('idx_item_milvus_id', Item.milvus_id)
Index('idx_item_deleted', Item.deleted_at)
Index('idx_item_created_at', Item.created_at)
Index('idx_item_view_count', Item.view_count)
Index('idx_item_like_count', Item.like_count)
