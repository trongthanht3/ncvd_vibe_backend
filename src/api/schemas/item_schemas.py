"""
Item API schemas for request/response validation.

This module provides Pydantic models for item-related API operations
with proper validation and IDOR protection considerations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from .common_schemas import ListResponse


class ItemBase(BaseModel):
    """
    Base item schema with common fields.
    """
    title: str = Field(
        min_length=1,
        max_length=255,
        description="Item title"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Item description"
    )
    content: Optional[str] = Field(
        default=None,
        description="Main item content"
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Item category"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Item tags"
    )
    is_public: bool = Field(
        default=False,
        description="Whether the item is publicly visible"
    )

    @validator('tags')
    def validate_tags(cls, v):
        """Validate and clean tags."""
        if v is not None:
            # Remove duplicates and empty tags, limit to 10 tags
            cleaned_tags = list(set([tag.strip().lower()
                                for tag in v if tag.strip()]))
            return cleaned_tags[:10]
        return v


class ItemCreate(ItemBase):
    """
    Schema for creating a new item.
    """
    pass


class ItemUpdate(BaseModel):
    """
    Schema for updating item information.
    """
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New item title"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="New item description"
    )
    content: Optional[str] = Field(
        default=None,
        description="New item content"
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="New item category"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="New item tags"
    )
    is_public: Optional[bool] = Field(
        default=None,
        description="New visibility status"
    )

    @validator('tags')
    def validate_tags(cls, v):
        """Validate and clean tags."""
        if v is not None:
            # Remove duplicates and empty tags, limit to 10 tags
            cleaned_tags = list(set([tag.strip().lower()
                                for tag in v if tag.strip()]))
            return cleaned_tags[:10]
        return v


class ItemResponse(ItemBase):
    """
    Schema for item response data.
    """
    id: UUID = Field(description="Item ID")
    owner_id: UUID = Field(description="Owner user ID")
    is_featured: bool = Field(description="Whether the item is featured")
    has_embedding: bool = Field(
        description="Whether the item has vector embedding")
    view_count: int = Field(description="Number of views")
    like_count: int = Field(description="Number of likes")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    # Optional embedding information (only shown to owner or admins)
    milvus_id: Optional[str] = Field(
        default=None,
        description="Milvus vector ID"
    )
    embedding_model: Optional[str] = Field(
        default=None,
        description="Embedding model used"
    )
    embedding_version: Optional[str] = Field(
        default=None,
        description="Embedding model version"
    )

    class Config:
        from_attributes = True


class ItemPublicResponse(BaseModel):
    """
    Schema for public item response (limited fields for non-owners).
    """
    id: UUID = Field(description="Item ID")
    title: str = Field(description="Item title")
    description: Optional[str] = Field(description="Item description")
    category: Optional[str] = Field(description="Item category")
    tags: Optional[List[str]] = Field(description="Item tags")
    is_featured: bool = Field(description="Whether the item is featured")
    view_count: int = Field(description="Number of views")
    like_count: int = Field(description="Number of likes")
    created_at: datetime = Field(description="Creation timestamp")

    class Config:
        from_attributes = True


class ItemListResponse(ListResponse):
    """
    Response schema for item list endpoints.
    """
    items: List[ItemResponse] = Field(description="List of items")


class ItemPublicListResponse(ListResponse):
    """
    Response schema for public item list endpoints.
    """
    items: List[ItemPublicResponse] = Field(description="List of public items")


class ItemStatsUpdate(BaseModel):
    """
    Schema for updating item statistics.
    """
    increment_views: bool = Field(
        default=False,
        description="Whether to increment view count"
    )
    increment_likes: bool = Field(
        default=False,
        description="Whether to increment like count"
    )
    decrement_likes: bool = Field(
        default=False,
        description="Whether to decrement like count"
    )


class ItemVisibilityUpdate(BaseModel):
    """
    Schema for updating item visibility.
    """
    is_public: bool = Field(description="New visibility status")


class ItemFeaturedUpdate(BaseModel):
    """
    Schema for updating item featured status (admin only).
    """
    is_featured: bool = Field(description="New featured status")
