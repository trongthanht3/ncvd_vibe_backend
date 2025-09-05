"""
Pagination dependencies for FastAPI endpoints.

This module provides standardized pagination parameters and utilities
for consistent pagination across all API endpoints.
"""

from fastapi import Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class PaginationParams(BaseModel):
    """
    Pagination parameters for API endpoints.

    Provides standardized pagination with configurable limits
    and offset-based navigation.
    """
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-based)"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)"
    )

    @property
    def offset(self) -> int:
        """Calculate offset based on page and limit."""
        return (self.page - 1) * self.limit


class SearchParams(BaseModel):
    """
    Search parameters for API endpoints.

    Provides standardized search functionality with optional
    query string and sorting options.
    """
    q: Optional[str] = Field(
        default=None,
        description="Search query string"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="Field to sort by"
    )
    sort_order: str = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort order: asc or desc"
    )


async def get_pagination_params(
    page: int = Query(
        default=1,
        ge=1,
        description="Page number (1-based)",
        example=1
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
        example=20
    )
) -> PaginationParams:
    """
    FastAPI dependency to get pagination parameters.

    Validates and normalizes pagination parameters from query string.

    Args:
        page: Page number (1-based)
        limit: Items per page (max 100)

    Returns:
        PaginationParams: Validated pagination parameters
    """
    return PaginationParams(page=page, limit=limit)


async def get_search_params(
    q: Optional[str] = Query(
        default=None,
        description="Search query string",
        example="search terms"
    ),
    sort_by: Optional[str] = Query(
        default=None,
        description="Field to sort by",
        example="created_at"
    ),
    sort_order: str = Query(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort order",
        example="desc"
    )
) -> SearchParams:
    """
    FastAPI dependency to get search parameters.

    Validates and normalizes search parameters from query string.

    Args:
        q: Search query string
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)

    Returns:
        SearchParams: Validated search parameters
    """
    return SearchParams(q=q, sort_by=sort_by, sort_order=sort_order)


def create_pagination_metadata(
    total_items: int,
    page: int,
    limit: int,
    base_url: str = ""
) -> Dict[str, Any]:
    """
    Create pagination metadata for API responses.

    Calculates pagination information including total pages,
    navigation links, and current position.

    Args:
        total_items: Total number of items available
        page: Current page number
        limit: Items per page
        base_url: Base URL for navigation links

    Returns:
        Dict containing pagination metadata
    """
    total_pages = (total_items + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1

    metadata = {
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page,
        "items_per_page": limit,
        "has_next": has_next,
        "has_prev": has_prev,
        "offset": (page - 1) * limit
    }

    # Add navigation links if base_url provided
    if base_url:
        metadata["links"] = {}

        if has_next:
            metadata["links"]["next"] = f"{base_url}?page={page + 1}&limit={limit}"

        if has_prev:
            metadata["links"]["prev"] = f"{base_url}?page={page - 1}&limit={limit}"

        metadata["links"]["first"] = f"{base_url}?page=1&limit={limit}"
        metadata["links"]["last"] = f"{base_url}?page={total_pages}&limit={limit}"

    return metadata
