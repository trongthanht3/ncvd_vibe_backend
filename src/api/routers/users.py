"""
User management API endpoints.

This module demonstrates the proper implementation of the new 3-layer architecture:
- Presentation Layer: FastAPI routers with validation and documentation
- Application Layer: Business logic via UserService with IDOR protection
- Data Layer: Repository pattern with async database operations

Example Usage:
- GET /users/me - Get current user profile
- GET /users/{user_id} - Get user by ID (with IDOR protection)
- PUT /users/{user_id} - Update user (with ownership verification)
- GET /users - List users with pagination and search
- DELETE /users/{user_id} - Delete user (admin only)
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse

from ..schemas.user_schemas import (
    UserResponse,
    UserUpdate,
    UserCreate,
    UserListResponse
)
from ..schemas.common_schemas import (
    SuccessResponse,
    ErrorResponse
)
from ..deps.auth import (
    get_current_user,
    get_current_user_id,
    require_admin
)
from ..deps.services import get_user_service
from ..deps.pagination import (
    get_pagination_params,
    get_search_params,
    PaginationParams,
    SearchParams,
    create_pagination_metadata
)
from ...application.services.user_service import UserService
from ...core.exceptions import (
    NotFoundError,
    ForbiddenError,
    ValidationError
)

# Create router with proper tags and metadata
router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access forbidden"},
        404: {"model": ErrorResponse, "description": "User not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    }
)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the profile information for the currently authenticated user."
)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    Get the current authenticated user's profile.

    This endpoint demonstrates:
    - Simple authentication dependency injection
    - Direct return of user data without additional service calls
    - Proper response model typing
    """
    return current_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    description="Get a specific user's profile. Users can only access their own profile unless they are admin."
)
async def get_user_by_id(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """
    Get a user by ID with IDOR protection.

    This endpoint demonstrates:
    - IDOR protection via service layer
    - Proper exception handling and transformation
    - Business logic delegation to service layer
    """
    try:
        user = await user_service.get_user_by_id(user_id, current_user.id)
        return user
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user profile",
    description="Update a user's profile. Users can only update their own profile unless they are admin."
)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """
    Update a user with ownership verification.

    This endpoint demonstrates:
    - Request body validation with Pydantic schemas
    - IDOR protection for update operations
    - Service layer handling of business logic
    """
    try:
        updated_user = await user_service.update_user(
            user_id,
            user_update,
            current_user_id=current_user.id
        )
        return updated_user
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    description="Get a paginated list of users with optional search functionality. Admin access required."
)
async def list_users(
    pagination: PaginationParams = Depends(get_pagination_params),
    search: SearchParams = Depends(get_search_params),
    current_user: UserResponse = Depends(require_admin()),
    user_service: UserService = Depends(get_user_service)
) -> UserListResponse:
    """
    List users with pagination and search.

    This endpoint demonstrates:
    - Role-based access control (admin only)
    - Pagination parameter injection
    - Search parameter handling
    - Complex response model with metadata
    """
    try:
        # Get paginated users from service
        users, total_count = await user_service.search_users(
            query=search.q,
            limit=pagination.limit,
            offset=pagination.offset,
            sort_by=search.sort_by,
            sort_order=search.sort_order
        )

        # Create pagination metadata
        pagination_meta = create_pagination_metadata(
            total_items=total_count,
            page=pagination.page,
            limit=pagination.limit,
            base_url="/api/v1/users"
        )

        return UserListResponse(
            items=users,
            total=total_count,
            skip=pagination.offset,
            limit=pagination.limit,
            has_more=pagination.offset + len(users) < total_count
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user",
    description="Create a new user account. Admin access required."
)
async def create_user(
    user_create: UserCreate,
    current_user: UserResponse = Depends(require_admin()),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """
    Create a new user account.

    This endpoint demonstrates:
    - Admin-only access control
    - Request body validation
    - Service layer business logic
    - Proper HTTP status codes
    """
    try:
        new_user = await user_service.create_user(user_create)
        return new_user
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    summary="Delete user",
    description="Delete a user account. Admin access required."
)
async def delete_user(
    user_id: UUID,
    current_user: UserResponse = Depends(require_admin()),
    user_service: UserService = Depends(get_user_service)
) -> SuccessResponse:
    """
    Delete a user account.

    This endpoint demonstrates:
    - Admin-only access control
    - Soft delete via service layer
    - Success response formatting
    """
    try:
        await user_service.delete_user(user_id)
        return SuccessResponse(
            message="User deleted successfully"
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.get(
    "/{user_id}/stats",
    summary="Get user statistics",
    description="Get statistics for a specific user. Users can only access their own stats unless they are admin."
)
async def get_user_stats(
    user_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """
    Get user statistics.

    This endpoint demonstrates:
    - Custom response without predefined schema
    - IDOR protection for statistics access
    - Complex business logic delegation
    """
    try:
        stats = await user_service.get_user_statistics(
            user_id,
            current_user_id=current_user.id
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "user_id": str(user_id),
                "statistics": stats,
                "generated_at": "2024-01-01T00:00:00Z"  # Would be actual timestamp
            }
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
