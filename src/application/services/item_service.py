"""
Item service implementation with business logic and IDOR protection.

This module provides high-level item operations with comprehensive security features
including ownership verification, visibility controls, and audit logging.
"""

from typing import List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ...api.schemas.item_schemas import (
    ItemCreate,
    ItemUpdate,
    ItemResponse,
    ItemPublicResponse,
    ItemVisibilityUpdate
)
from ...core.exceptions import (
    NotFoundError,
    ForbiddenError,
    ValidationError
)
from ...data.repositories.item_repository import ItemRepository
from ...data.models.item import Item


class ItemService:
    """
    Item service providing business logic for item operations.

    Implements strong IDOR protection, visibility controls, and comprehensive
    audit logging for security compliance. All operations validate ownership
    and apply appropriate access controls.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize item service.

        Args:
            session: Async database session
        """
        self.session = session
        self.item_repo = ItemRepository(session)

    async def create_item(
        self,
        item_data: ItemCreate,
        owner_id: UUID
    ) -> ItemResponse:
        """
        Create a new item with ownership assignment.

        Args:
            item_data: Item creation data
            owner_id: ID of the user creating the item

        Returns:
            Created item data

        Raises:
            ValidationError: If item data is invalid
        """
        logger.info(
            f"Creating item '{item_data.title}' for user {owner_id}",
            extra={"owner_id": str(owner_id), "title": item_data.title}
        )

        try:
            # Create item with owner assignment
            item = await self.item_repo.create(item_data.model_dump(), owner_id=owner_id)
            await self.session.commit()

            logger.info(
                f"Item created successfully: {item.id}",
                extra={"item_id": str(item.id), "owner_id": str(owner_id)}
            )

            return ItemResponse.model_validate(item)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create item: {str(e)}")
            raise ValidationError(f"Failed to create item: {str(e)}")

    async def get_item_by_id(
        self,
        item_id: UUID,
        requesting_user_id: Optional[UUID] = None,
        requesting_user_role: str = "user"
    ) -> ItemResponse:
        """
        Get item by ID with visibility and ownership checks.

        Args:
            item_id: ID of item to retrieve
            requesting_user_id: ID of user making the request (None for anonymous)
            requesting_user_role: Role of requesting user

        Returns:
            Item data (full or public based on access rights)

        Raises:
            NotFoundError: If item not found or access denied
        """
        item = await self.item_repo.get(item_id)
        if not item:
            raise NotFoundError(f"Item with ID {item_id} not found")

        # Check visibility permissions
        can_access = self._can_access_item(
            item, requesting_user_id, requesting_user_role)
        if not can_access:
            # Don't reveal existence
            raise NotFoundError(f"Item with ID {item_id} not found")

        # Increment view count for public access or when viewing own items
        if requesting_user_id != item.owner_id:
            await self.item_repo.increment_view_count(item_id)
            await self.session.commit()

        # Return full data for owners/admins, public data for others
        if self._is_owner_or_admin(item, requesting_user_id, requesting_user_role):
            return ItemResponse.model_validate(item)
        else:
            return ItemPublicResponse.model_validate(item)

    async def update_item(
        self,
        item_id: UUID,
        item_data: ItemUpdate,
        requesting_user_id: UUID,
        requesting_user_role: str = "user"
    ) -> ItemResponse:
        """
        Update item with IDOR protection.

        Args:
            item_id: ID of item to update
            item_data: Update data
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user

        Returns:
            Updated item data

        Raises:
            NotFoundError: If item not found
            ForbiddenError: If access denied (IDOR protection)
        """
        # IDOR Protection: Only owners and admins can update items
        if requesting_user_role != "admin":
            item = await self.item_repo.get_by_owner(item_id, requesting_user_id)
            if not item:
                logger.warning(
                    f"IDOR attempt: User {requesting_user_id} tried to update item {item_id}",
                    extra={"requesting_user": str(
                        requesting_user_id), "item_id": str(item_id)}
                )
                # Don't reveal existence
                raise NotFoundError(f"Item with ID {item_id} not found")

        try:
            updated_item = await self.item_repo.update(
                item_id,
                item_data.model_dump(exclude_unset=True),
                owner_id=requesting_user_id if requesting_user_role != "admin" else None
            )

            if not updated_item:
                raise NotFoundError(f"Item with ID {item_id} not found")

            await self.session.commit()

            logger.info(
                f"Item updated successfully: {item_id}",
                extra={"item_id": str(item_id), "updated_by": str(
                    requesting_user_id)}
            )

            return ItemResponse.model_validate(updated_item)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update item {item_id}: {str(e)}")
            raise ValidationError(f"Failed to update item: {str(e)}")

    async def delete_item(
        self,
        item_id: UUID,
        requesting_user_id: UUID,
        requesting_user_role: str = "user"
    ) -> bool:
        """
        Delete item with IDOR protection.

        Args:
            item_id: ID of item to delete
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If item not found
            ForbiddenError: If access denied (IDOR protection)
        """
        # IDOR Protection: Only owners and admins can delete items
        owner_id = requesting_user_id if requesting_user_role != "admin" else None

        success = await self.item_repo.delete(item_id, owner_id=owner_id)
        if not success:
            logger.warning(
                f"IDOR attempt: User {requesting_user_id} tried to delete item {item_id}",
                extra={"requesting_user": str(
                    requesting_user_id), "item_id": str(item_id)}
            )
            raise NotFoundError(f"Item with ID {item_id} not found")

        await self.session.commit()

        logger.warning(
            f"Item deleted: {item_id}",
            extra={"item_id": str(item_id), "deleted_by": str(
                requesting_user_id)}
        )

        return True

    async def get_user_items(
        self,
        owner_id: UUID,
        requesting_user_id: Optional[UUID] = None,
        requesting_user_role: str = "user",
        skip: int = 0,
        limit: int = 100,
        include_private: bool = False
    ) -> List[ItemResponse]:
        """
        Get items belonging to a user with privacy controls.

        Args:
            owner_id: ID of user whose items to retrieve
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of requesting user
            skip: Pagination offset
            limit: Pagination limit
            include_private: Whether to include private items

        Returns:
            List of user's items
        """
        # Privacy control: Only show private items to owner or admin
        show_private = (
            include_private and
            (requesting_user_id == owner_id or requesting_user_role == "admin")
        )

        items = await self.item_repo.get_user_items(
            owner_id=owner_id,
            skip=skip,
            limit=limit,
            include_private=show_private
        )

        # Return appropriate response type based on access level
        if requesting_user_id == owner_id or requesting_user_role == "admin":
            return [ItemResponse.model_validate(item) for item in items]
        else:
            return [ItemPublicResponse.model_validate(item) for item in items]

    async def get_public_items(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        featured_only: bool = False
    ) -> List[ItemPublicResponse]:
        """
        Get public items with optional filtering.

        Args:
            skip: Pagination offset
            limit: Pagination limit
            category: Optional category filter
            featured_only: Only return featured items

        Returns:
            List of public items
        """
        items = await self.item_repo.get_public_items(
            skip=skip,
            limit=limit,
            category=category,
            featured_only=featured_only
        )

        return [ItemPublicResponse.model_validate(item) for item in items]

    async def search_items(
        self,
        query: str,
        requesting_user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ItemPublicResponse]:
        """
        Search items with visibility controls.

        Args:
            query: Search query string
            requesting_user_id: ID of user making the request (None for anonymous)
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of matching items
        """
        items = await self.item_repo.search(query, owner_id=requesting_user_id)
        return [ItemPublicResponse.model_validate(item) for item in items[:limit]]

    async def toggle_item_like(
        self,
        item_id: UUID,
        requesting_user_id: UUID,
        increment: bool = True
    ) -> bool:
        """
        Toggle like count for an item with access controls.

        Args:
            item_id: ID of item to like/unlike
            requesting_user_id: ID of user performing the action
            increment: True to like, False to unlike

        Returns:
            True if toggled successfully

        Raises:
            NotFoundError: If item not found or access denied
        """
        success = await self.item_repo.toggle_like(
            item_id=item_id,
            owner_id=requesting_user_id,
            increment=increment
        )

        if not success:
            raise NotFoundError(f"Item with ID {item_id} not found")

        await self.session.commit()

        action = "liked" if increment else "unliked"
        logger.info(
            f"Item {action}: {item_id}",
            extra={"item_id": str(item_id), "user_id": str(
                requesting_user_id), "action": action}
        )

        return True

    async def update_item_visibility(
        self,
        item_id: UUID,
        visibility_data: ItemVisibilityUpdate,
        requesting_user_id: UUID
    ) -> bool:
        """
        Update item visibility with IDOR protection.

        Args:
            item_id: ID of item to update
            visibility_data: New visibility settings
            requesting_user_id: ID of user making the request

        Returns:
            True if updated successfully

        Raises:
            NotFoundError: If item not found or access denied
        """
        success = await self.item_repo.update_visibility(
            item_id=item_id,
            owner_id=requesting_user_id,
            is_public=visibility_data.is_public
        )

        if not success:
            raise NotFoundError(f"Item with ID {item_id} not found")

        await self.session.commit()

        visibility = "public" if visibility_data.is_public else "private"
        logger.info(
            f"Item visibility updated to {visibility}: {item_id}",
            extra={"item_id": str(item_id), "owner_id": str(
                requesting_user_id), "visibility": visibility}
        )

        return True

    def _can_access_item(
        self,
        item: Item,
        requesting_user_id: Optional[UUID],
        requesting_user_role: str
    ) -> bool:
        """
        Check if user can access an item based on visibility and ownership.

        Args:
            item: Item to check access for
            requesting_user_id: ID of requesting user
            requesting_user_role: Role of requesting user

        Returns:
            True if user can access the item
        """
        # Admins can access everything
        if requesting_user_role == "admin":
            return True

        # Owners can access their own items
        if requesting_user_id and item.owner_id == requesting_user_id:
            return True

        # Anyone can access public items
        if item.is_public:
            return True

        return False

    def _is_owner_or_admin(
        self,
        item: Item,
        requesting_user_id: Optional[UUID],
        requesting_user_role: str
    ) -> bool:
        """
        Check if user is owner or admin for full data access.

        Args:
            item: Item to check ownership for
            requesting_user_id: ID of requesting user
            requesting_user_role: Role of requesting user

        Returns:
            True if user is owner or admin
        """
        return (
            requesting_user_role == "admin" or
            (requesting_user_id and item.owner_id == requesting_user_id)
        )
