"""
Common API schemas for shared data structures.

This module provides common Pydantic models used across different API endpoints
for consistent request/response handling.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """
    Common pagination parameters for list endpoints.
    """
    skip: int = Field(
        default=0,
        ge=0,
        description="Number of records to skip"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of records to return"
    )


class ErrorResponse(BaseModel):
    """
    Standard error response format.
    """
    error: str = Field(description="Error message")
    detail: Optional[str] = Field(
        default=None, description="Detailed error information")
    error_code: Optional[str] = Field(
        default=None, description="Application-specific error code")
    correlation_id: Optional[str] = Field(
        default=None, description="Request correlation ID")


class SuccessResponse(BaseModel):
    """
    Standard success response format.
    """
    message: str = Field(description="Success message")
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Response data")
    correlation_id: Optional[str] = Field(
        default=None, description="Request correlation ID")


class ListResponse(BaseModel):
    """
    Standard list response format with pagination metadata.
    """
    items: List[Any] = Field(description="List of items")
    total: int = Field(description="Total number of items available")
    skip: int = Field(description="Number of items skipped")
    limit: int = Field(description="Maximum number of items returned")
    has_more: bool = Field(
        description="Whether there are more items available")


class IdResponse(BaseModel):
    """
    Simple response containing just an ID.
    """
    id: UUID = Field(description="Resource ID")


class CountResponse(BaseModel):
    """
    Response containing a count value.
    """
    count: int = Field(description="Count value")


class StatusResponse(BaseModel):
    """
    Response for status operations.
    """
    success: bool = Field(description="Whether the operation was successful")
    message: Optional[str] = Field(default=None, description="Status message")
