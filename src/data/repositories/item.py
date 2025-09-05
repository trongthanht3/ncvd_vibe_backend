"""
Item repository for item-specific database operations.

This module defines the ItemRepository class that extends BaseRepository
with item-specific query methods.
"""

from typing import Dict, List, Optional
import uuid

from sqlalchemy import select, func, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.item import Item
from .base import BaseRepository


class ItemRepository(BaseRepository[Item]):
    """
    Repository class for Item entities.

    Provides item-specific database operations extending the base
    CRUD functionality.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the item repository.

        Args:
            session: Async database session
        """
        super().__init__(Item, session)

    async def get_by_owner(
        self,
        owner_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Item]:
        """
        Get items by owner ID.

        Args:
            owner_id: Owner user ID
            skip: Number of items to skip
            limit: Maximum number of items to return
            include_deleted: Whether to include soft-deleted items

        Returns:
            List of items owned by the user
        """
        return await self.find_by_fields(
            filters={'owner_id': owner_id},
            skip=skip,
            limit=limit,
            include_deleted=include_deleted,
            order_by='created_at'
        )

    async def get_public_items(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = 'created_at'
    ) -> List[Item]:
        """
        Get public items.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            order_by: Field to order by

        Returns:
            List of public items
        """
        return await self.find_by_fields(
            filters={'is_public': True},
            skip=skip,
            limit=limit,
            order_by=order_by
        )

    async def get_featured_items(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """
        Get featured items.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return

        Returns:
            List of featured items
        """
        return await self.find_by_fields(
            filters={'is_featured': True, 'is_public': True},
            skip=skip,
            limit=limit,
            order_by='view_count'
        )

    async def get_by_category(
        self,
        category: str,
        skip: int = 0,
        limit: int = 100,
        public_only: bool = True
    ) -> List[Item]:
        """
        Get items by category.

        Args:
            category: Category to filter by
            skip: Number of items to skip
            limit: Maximum number of items to return
            public_only: Whether to only return public items

        Returns:
            List of items in the specified category
        """
        filters = {'category': category}
        if public_only:
            filters['is_public'] = True

        return await self.find_by_fields(
            filters=filters,
            skip=skip,
            limit=limit,
            order_by='created_at'
        )

    async def search_items(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        public_only: bool = True,
        owner_id: Optional[uuid.UUID] = None
    ) -> List[Item]:
        """
        Search items by title and description.

        Args:
            search_term: Term to search for
            skip: Number of items to skip
            limit: Maximum number of items to return
            public_only: Whether to only search public items
            owner_id: Optional owner ID to filter by

        Returns:
            List of matching items
        """
        search_pattern = f"%{search_term.lower()}%"

        query = select(self.model).where(
            or_(
                func.lower(self.model.title).like(search_pattern),
                func.lower(self.model.description).like(search_pattern),
                func.lower(self.model.content).like(search_pattern)
            )
        )

        if public_only:
            query = query.where(self.model.is_public == True)

        if owner_id:
            query = query.where(self.model.owner_id == owner_id)

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        query = query.order_by(desc(self.model.view_count)
                               ).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_items_with_embeddings(
        self,
        skip: int = 0,
        limit: int = 100,
        model_name: Optional[str] = None
    ) -> List[Item]:
        """
        Get items that have vector embeddings.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            model_name: Optional embedding model to filter by

        Returns:
            List of items with embeddings
        """
        filters = {'has_embedding': True}
        if model_name:
            filters['embedding_model'] = model_name

        return await self.find_by_fields(
            filters=filters,
            skip=skip,
            limit=limit,
            order_by='created_at'
        )

    async def get_by_milvus_id(self, milvus_id: str) -> Optional[Item]:
        """
        Get item by Milvus vector ID.

        Args:
            milvus_id: Milvus vector ID

        Returns:
            Item instance or None if not found
        """
        return await self.find_one_by_fields({'milvus_id': milvus_id})

    async def get_popular_items(
        self,
        skip: int = 0,
        limit: int = 100,
        time_range_days: Optional[int] = None
    ) -> List[Item]:
        """
        Get popular items by view count.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            time_range_days: Optional time range in days

        Returns:
            List of popular items
        """
        query = select(self.model).where(
            and_(
                self.model.is_public == True,
                self.model.view_count > 0
            )
        )

        if time_range_days and hasattr(self.model, 'created_at'):
            cutoff_date = func.now() - func.interval(f'{time_range_days} days')
            query = query.where(self.model.created_at >= cutoff_date)

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        query = (
            query
            .order_by(desc(self.model.view_count), desc(self.model.like_count))
            .offset(skip)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_items_by_tags(
        self,
        tags: List[str],
        skip: int = 0,
        limit: int = 100,
        public_only: bool = True
    ) -> List[Item]:
        """
        Get items that contain any of the specified tags.

        Args:
            tags: List of tags to search for
            skip: Number of items to skip
            limit: Maximum number of items to return
            public_only: Whether to only return public items

        Returns:
            List of items containing the tags
        """
        query = select(self.model).where(
            self.model.tags.op('@>')([tag]) for tag in tags
        )

        if public_only:
            query = query.where(self.model.is_public == True)

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        query = query.order_by(desc(self.model.created_at)
                               ).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def increment_view_count(self, item_id: uuid.UUID) -> Optional[Item]:
        """
        Increment view count for an item.

        Args:
            item_id: Item ID

        Returns:
            Updated item instance or None if not found
        """
        item = await self.get_by_id(item_id)
        if item:
            item.increment_view_count()
            await self.session.flush()
            await self.session.refresh(item)
        return item

    async def increment_like_count(self, item_id: uuid.UUID) -> Optional[Item]:
        """
        Increment like count for an item.

        Args:
            item_id: Item ID

        Returns:
            Updated item instance or None if not found
        """
        item = await self.get_by_id(item_id)
        if item:
            item.increment_like_count()
            await self.session.flush()
            await self.session.refresh(item)
        return item

    async def decrement_like_count(self, item_id: uuid.UUID) -> Optional[Item]:
        """
        Decrement like count for an item.

        Args:
            item_id: Item ID

        Returns:
            Updated item instance or None if not found
        """
        item = await self.get_by_id(item_id)
        if item:
            item.decrement_like_count()
            await self.session.flush()
            await self.session.refresh(item)
        return item

    async def update_embedding_info(
        self,
        item_id: uuid.UUID,
        milvus_id: str,
        model: str,
        version: str
    ) -> Optional[Item]:
        """
        Update embedding information for an item.

        Args:
            item_id: Item ID
            milvus_id: Milvus vector ID
            model: Embedding model name
            version: Embedding model version

        Returns:
            Updated item instance or None if not found
        """
        item = await self.get_by_id(item_id)
        if item:
            item.set_embedding_info(milvus_id, model, version)
            await self.session.flush()
            await self.session.refresh(item)
        return item

    async def clear_embedding_info(self, item_id: uuid.UUID) -> Optional[Item]:
        """
        Clear embedding information for an item.

        Args:
            item_id: Item ID

        Returns:
            Updated item instance or None if not found
        """
        item = await self.get_by_id(item_id)
        if item:
            item.clear_embedding_info()
            await self.session.flush()
            await self.session.refresh(item)
        return item

    async def get_items_with_owner(
        self,
        skip: int = 0,
        limit: int = 100,
        public_only: bool = True
    ) -> List[Item]:
        """
        Get items with owner information loaded.

        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            public_only: Whether to only return public items

        Returns:
            List of items with owner relationship loaded
        """
        query = (
            select(self.model)
            .options(selectinload(self.model.owner))
            .where(self.model.deleted_at.is_(None))
        )

        if public_only:
            query = query.where(self.model.is_public == True)

        query = query.order_by(desc(self.model.created_at)
                               ).offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_owner(self, owner_id: uuid.UUID) -> int:
        """
        Count items by owner.

        Args:
            owner_id: Owner user ID

        Returns:
            Count of items owned by the user
        """
        query = select(func.count(self.model.id)).where(
            and_(
                self.model.owner_id == owner_id,
                self.model.deleted_at.is_(None)
            )
        )

        result = await self.session.execute(query)
        return result.scalar()

    async def count_public_items(self) -> int:
        """
        Count public items.

        Returns:
            Count of public items
        """
        query = select(func.count(self.model.id)).where(
            and_(
                self.model.is_public == True,
                self.model.deleted_at.is_(None)
            )
        )

        result = await self.session.execute(query)
        return result.scalar()
