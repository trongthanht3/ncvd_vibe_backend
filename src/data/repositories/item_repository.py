"""
Item repository implementation with IDOR protection.

This module provides secure item data access operations with built-in
ownership verification and vector search support.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, or_, select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.item import Item
from .base import BaseRepository


class ItemRepository(BaseRepository[Item, dict, dict]):
    """
    Repository for Item model operations.

    Provides secure CRUD operations with strong IDOR protection
    and support for public/private item visibility.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize item repository.

        Args:
            session: Async database session
        """
        super().__init__(Item, session)

    async def get_by_email(self, email: str) -> Optional[Item]:
        """
        Not applicable for items.

        Args:
            email: Not used for items

        Returns:
            None (items don't have emails)
        """
        return None

    async def search(self, query: str, owner_id: Optional[UUID] = None) -> List[Item]:
        """
        Search items by title, description, or content.

        Args:
            query: Search query string
            owner_id: Optional owner ID for filtering (IDOR protection)

        Returns:
            List of matching items
        """
        search_term = f"%{query.lower()}%"

        # Base search conditions
        conditions = [
            or_(
                self.model.title.ilike(search_term),
                self.model.description.ilike(search_term),
                self.model.content.ilike(search_term)
            ),
            self.model.deleted_at.is_(None)
        ]

        # Apply owner filter or public visibility
        if owner_id:
            # User can see their own items (public or private) + other users' public items
            conditions.append(
                or_(
                    self.model.owner_id == owner_id,
                    self.model.is_public == True
                )
            )
        else:
            # Anonymous users can only see public items
            conditions.append(self.model.is_public == True)

        stmt = select(self.model).where(
            and_(*conditions)
        ).order_by(desc(self.model.created_at)).limit(50)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_public_items(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        featured_only: bool = False
    ) -> List[Item]:
        """
        Get public items with optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            category: Optional category filter
            featured_only: Only return featured items

        Returns:
            List of public items
        """
        limit = min(limit, 1000)

        conditions = [
            self.model.is_public == True,
            self.model.deleted_at.is_(None)
        ]

        if category:
            conditions.append(self.model.category == category)

        if featured_only:
            conditions.append(self.model.is_featured == True)

        stmt = select(self.model).where(
            and_(*conditions)
        ).order_by(desc(self.model.created_at)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_items(
        self,
        owner_id: UUID,
        skip: int = 0,
        limit: int = 100,
        include_private: bool = True
    ) -> List[Item]:
        """
        Get items belonging to a specific user with IDOR protection.

        Args:
            owner_id: Owner ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_private: Whether to include private items

        Returns:
            List of user's items
        """
        limit = min(limit, 1000)

        conditions = [
            self.model.owner_id == owner_id,
            self.model.deleted_at.is_(None)
        ]

        if not include_private:
            conditions.append(self.model.is_public == True)

        stmt = select(self.model).where(
            and_(*conditions)
        ).order_by(desc(self.model.created_at)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(
        self,
        category: str,
        owner_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """
        Get items by category with optional owner filtering.

        Args:
            category: Category to filter by
            owner_id: Optional owner ID for private items access
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of items in the category
        """
        limit = min(limit, 1000)

        conditions = [
            self.model.category == category,
            self.model.deleted_at.is_(None)
        ]

        # Apply visibility rules
        if owner_id:
            conditions.append(
                or_(
                    self.model.owner_id == owner_id,
                    self.model.is_public == True
                )
            )
        else:
            conditions.append(self.model.is_public == True)

        stmt = select(self.model).where(
            and_(*conditions)
        ).order_by(desc(self.model.created_at)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_featured_items(self, skip: int = 0, limit: int = 100) -> List[Item]:
        """
        Get featured public items.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of featured items
        """
        return await self.get_public_items(
            skip=skip,
            limit=limit,
            featured_only=True
        )

    async def get_items_with_embeddings(
        self,
        owner_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """
        Get items that have vector embeddings.

        Args:
            owner_id: Optional owner ID for filtering
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of items with embeddings
        """
        limit = min(limit, 1000)

        conditions = [
            self.model.has_embedding == True,
            self.model.milvus_id.is_not(None),
            self.model.deleted_at.is_(None)
        ]

        # Apply visibility rules
        if owner_id:
            conditions.append(
                or_(
                    self.model.owner_id == owner_id,
                    self.model.is_public == True
                )
            )
        else:
            conditions.append(self.model.is_public == True)

        stmt = select(self.model).where(
            and_(*conditions)
        ).order_by(desc(self.model.created_at)).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_view_count(self, item_id: UUID) -> bool:
        """
        Increment view count for an item.

        Args:
            item_id: ID of item to increment views for

        Returns:
            True if incremented, False if item not found
        """
        item = await self.get(item_id)
        if item:
            item.increment_view_count()
            await self.session.flush()
            return True
        return False

    async def toggle_like(self, item_id: UUID, owner_id: UUID, increment: bool = True) -> bool:
        """
        Toggle like count for an item (with owner verification for private items).

        Args:
            item_id: ID of item to toggle like for
            owner_id: ID of user performing the action
            increment: True to increment, False to decrement

        Returns:
            True if toggled, False if item not found or access denied
        """
        # Get item with visibility check
        conditions = [
            self.model.id == item_id,
            self.model.deleted_at.is_(None),
            or_(
                self.model.owner_id == owner_id,  # User's own item
                self.model.is_public == True      # Public item
            )
        ]

        stmt = select(self.model).where(and_(*conditions))
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()

        if item:
            if increment:
                item.increment_like_count()
            else:
                item.decrement_like_count()
            await self.session.flush()
            return True
        return False

    async def update_visibility(
        self,
        item_id: UUID,
        owner_id: UUID,
        is_public: bool
    ) -> bool:
        """
        Update item visibility with IDOR protection.

        Args:
            item_id: ID of item to update
            owner_id: Owner ID for verification
            is_public: New visibility status

        Returns:
            True if updated, False if not found or not owned
        """
        item = await self.get_by_owner(item_id, owner_id)
        if item:
            item.is_public = is_public
            await self.session.flush()
            return True
        return False

    async def set_featured_status(
        self,
        item_id: UUID,
        is_featured: bool,
        admin_user_id: UUID
    ) -> bool:
        """
        Set featured status for an item (admin only).

        Args:
            item_id: ID of item to update
            is_featured: New featured status
            admin_user_id: ID of admin user performing action

        Returns:
            True if updated, False if not found

        Note:
            This method should be wrapped with role-based authorization
            in the service layer to ensure only admins can use it.
        """
        item = await self.get(item_id)
        if item:
            item.is_featured = is_featured
            await self.session.flush()
            return True
        return False

    async def get_popular_items(
        self,
        skip: int = 0,
        limit: int = 100,
        time_period_days: Optional[int] = None
    ) -> List[Item]:
        """
        Get popular items sorted by view/like counts.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            time_period_days: Optional time period filter (not implemented yet)

        Returns:
            List of popular items
        """
        limit = min(limit, 1000)

        conditions = [
            self.model.is_public == True,
            self.model.deleted_at.is_(None)
        ]

        # TODO: Add time period filtering when needed
        # if time_period_days:
        #     cutoff_date = datetime.utcnow() - timedelta(days=time_period_days)
        #     conditions.append(self.model.created_at >= cutoff_date)

        stmt = select(self.model).where(
            and_(*conditions)
        ).order_by(
            desc(self.model.like_count),
            desc(self.model.view_count),
            desc(self.model.created_at)
        ).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
