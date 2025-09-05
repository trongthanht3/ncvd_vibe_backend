"""
Item management API endpoints.

This module demonstrates the new 3-layer architecture patterns:
- Repository pattern for data access
- Service layer for business logic with IDOR protection
- Proper validation and error handling

Example Usage:
- GET /items - List all public items
- POST /items - Create new item with automatic ownership
- GET /items/{item_id} - Get item details with permission checks
- PUT /items/{item_id} - Update item with ownership verification
- DELETE /items/{item_id} - Delete item with ownership verification
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from ..schemas.item_schemas import (
    ItemResponse,
    ItemCreate,
    ItemUpdate,
    ItemListResponse,
    ItemPublicListResponse
)
from ..schemas.common_schemas import (
    SuccessResponse,
    ErrorResponse,
    PaginationParams
)
from ..deps.auth import (
    get_current_user,
    get_optional_current_user,
    get_current_user_id
)
from ..deps.services import get_item_service
from ...application.services.item_service import ItemService
from ...api.schemas.user_schemas import UserResponse
from ...core.exceptions import (
    NotFoundError,
    ForbiddenError,
    ValidationError
)

# Create router with proper tags and documentation
router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access forbidden"},
        404: {"model": ErrorResponse, "description": "Item not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    }
)


@router.get(
    "",
    response_model=ItemPublicListResponse,
    summary="List items",
    description="Get a list of items. Returns public items for anonymous users."
)
async def list_items(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100,
                       description="Number of items to return"),
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    item_service: ItemService = Depends(get_item_service),
    category: Optional[str] = Query(
        default=None, description="Filter by category")
) -> ItemPublicListResponse:
    """
    List public items.

    This endpoint demonstrates:
    - Optional authentication for public access
    - Basic filtering and pagination
    - Service layer access control
    """
    try:
        user_id = current_user.id if current_user else None

        items, total_count = await item_service.search_items(
            user_id=user_id,
            category=category,
            include_private=False,
            limit=limit,
            offset=skip
        )

        return ItemPublicListResponse(
            items=items,
            total=total_count,
            skip=skip,
            limit=limit,
            has_more=skip + len(items) < total_count
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new item",
    description="Create a new item. Ownership is automatically assigned to the authenticated user."
)
async def create_item(
    item_create: ItemCreate,
    current_user_id: UUID = Depends(get_current_user_id),
    item_service: ItemService = Depends(get_item_service)
) -> ItemResponse:
    """
    Create a new item with automatic ownership.

    This endpoint demonstrates:
    - Automatic ownership assignment
    - Request validation with Pydantic schemas
    - Service layer business logic
    """
    try:
        new_item = await item_service.create_item(item_create, owner_id=current_user_id)
        return new_item
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Get item by ID",
    description="Get a specific item. Private items can only be accessed by their owner."
)
async def get_item_by_id(
    item_id: UUID,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    item_service: ItemService = Depends(get_item_service)
) -> ItemResponse:
    """
    Get an item by ID with IDOR protection.

    This endpoint demonstrates:
    - Optional authentication for public/private items
    - IDOR protection via service layer
    - Proper error handling
    """
    try:
        user_id = current_user.id if current_user else None
        item = await item_service.get_item_by_id(item_id, requester_id=user_id)
        return item
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to private item"
        )


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update item",
    description="Update an item. Only the owner can update their items."
)
async def update_item(
    item_id: UUID,
    item_update: ItemUpdate,
    current_user_id: UUID = Depends(get_current_user_id),
    item_service: ItemService = Depends(get_item_service)
) -> ItemResponse:
    """
    Update an item with ownership verification.

    This endpoint demonstrates:
    - Ownership verification for updates
    - Partial update handling
    - Business logic in service layer
    """
    try:
        updated_item = await item_service.update_item(
            item_id,
            item_update,
            owner_id=current_user_id
        )
        return updated_item
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - not item owner"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.delete(
    "/{item_id}",
    response_model=SuccessResponse,
    summary="Delete item",
    description="Delete an item. Only the owner can delete their items."
)
async def delete_item(
    item_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    item_service: ItemService = Depends(get_item_service)
) -> SuccessResponse:
    """
    Delete an item with ownership verification.

    This endpoint demonstrates:
    - Ownership verification for deletion
    - Service layer business logic
    - Proper success response
    """
    try:
        await item_service.delete_item(item_id, owner_id=current_user_id)
        return SuccessResponse(
            message="Item deleted successfully"
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - not item owner"
        )


@router.get(
    "/my-items",
    response_model=ItemListResponse,
    summary="Get current user's items",
    description="Get all items owned by the current authenticated user."
)
async def get_my_items(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=20, ge=1, le=100,
                       description="Number of items to return"),
    current_user_id: UUID = Depends(get_current_user_id),
    item_service: ItemService = Depends(get_item_service)
) -> ItemListResponse:
    """
    Get current user's items.

    This endpoint demonstrates:
    - User-specific data filtering
    - Owner-only access pattern
    - Proper pagination handling
    """
    try:
        items, total_count = await item_service.get_user_items(
            user_id=current_user_id,
            limit=limit,
            offset=skip
        )

        return ItemListResponse(
            items=items,
            total=total_count,
            skip=skip,
            limit=limit,
            has_more=skip + len(items) < total_count
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
