"""
Base repository class providing common CRUD operations.

This module defines the BaseRepository class that provides common
database operations for all entity repositories.
"""

from typing import Any, Dict, Generic, List, Optional, Sequence, TypeVar, Union
import uuid

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from ..models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Base repository class providing common CRUD operations.

    This class provides a generic interface for database operations
    that can be extended by specific model repositories.
    """

    def __init__(self, model: type[T], session: AsyncSession):
        """
        Initialize the repository.

        Args:
            model: The SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def create(self, obj_data: Dict[str, Any]) -> T:
        """
        Create a new entity.

        Args:
            obj_data: Dictionary of entity data

        Returns:
            Created entity instance
        """
        obj = self.model(**obj_data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def get_by_id(
        self,
        entity_id: Union[uuid.UUID, str],
        include_deleted: bool = False
    ) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            entity_id: Entity ID
            include_deleted: Whether to include soft-deleted entities

        Returns:
            Entity instance or None if not found
        """
        query = select(self.model).where(self.model.id == entity_id)

        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        order_by: Optional[str] = None
    ) -> List[T]:
        """
        Get all entities with pagination.

        Args:
            skip: Number of entities to skip
            limit: Maximum number of entities to return
            include_deleted: Whether to include soft-deleted entities
            order_by: Field to order by (default: created_at desc)

        Returns:
            List of entity instances
        """
        query = select(self.model)

        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        # Apply ordering
        if order_by:
            if hasattr(self.model, order_by):
                query = query.order_by(getattr(self.model, order_by))
        else:
            if hasattr(self.model, 'created_at'):
                query = query.order_by(self.model.created_at.desc())

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        entity_id: Union[uuid.UUID, str],
        update_data: Dict[str, Any]
    ) -> Optional[T]:
        """
        Update entity by ID.

        Args:
            entity_id: Entity ID
            update_data: Dictionary of fields to update

        Returns:
            Updated entity instance or None if not found
        """
        # Add updated_at timestamp if the model has it
        if hasattr(self.model, 'updated_at'):
            update_data['updated_at'] = func.now()

        query = (
            update(self.model)
            .where(self.model.id == entity_id)
            .values(**update_data)
            .returning(self.model)
        )

        if hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        updated_entity = result.scalar_one_or_none()

        if updated_entity:
            await self.session.refresh(updated_entity)

        return updated_entity

    async def delete(
        self,
        entity_id: Union[uuid.UUID, str],
        soft_delete: bool = True
    ) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Entity ID
            soft_delete: Whether to perform soft delete (if supported)

        Returns:
            True if entity was deleted, False if not found
        """
        if soft_delete and hasattr(self.model, 'deleted_at'):
            # Soft delete
            result = await self.update(entity_id, {'deleted_at': func.now()})
            return result is not None
        else:
            # Hard delete
            query = delete(self.model).where(self.model.id == entity_id)
            result = await self.session.execute(query)
            return result.rowcount > 0

    async def count(self, include_deleted: bool = False) -> int:
        """
        Count entities.

        Args:
            include_deleted: Whether to include soft-deleted entities

        Returns:
            Count of entities
        """
        query = select(func.count(self.model.id))

        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar()

    async def exists(
        self,
        entity_id: Union[uuid.UUID, str],
        include_deleted: bool = False
    ) -> bool:
        """
        Check if entity exists.

        Args:
            entity_id: Entity ID
            include_deleted: Whether to include soft-deleted entities

        Returns:
            True if entity exists, False otherwise
        """
        query = select(self.model.id).where(self.model.id == entity_id)

        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def find_by_fields(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        order_by: Optional[str] = None
    ) -> List[T]:
        """
        Find entities by field values.

        Args:
            filters: Dictionary of field:value pairs to filter by
            skip: Number of entities to skip
            limit: Maximum number of entities to return
            include_deleted: Whether to include soft-deleted entities
            order_by: Field to order by

        Returns:
            List of matching entities
        """
        query = select(self.model)

        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                if isinstance(value, list):
                    query = query.where(getattr(self.model, field).in_(value))
                else:
                    query = query.where(getattr(self.model, field) == value)

        if not include_deleted and hasattr(self.model, 'deleted_at'):
            query = query.where(self.model.deleted_at.is_(None))

        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            query = query.order_by(getattr(self.model, order_by))
        elif hasattr(self.model, 'created_at'):
            query = query.order_by(self.model.created_at.desc())

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_one_by_fields(
        self,
        filters: Dict[str, Any],
        include_deleted: bool = False
    ) -> Optional[T]:
        """
        Find single entity by field values.

        Args:
            filters: Dictionary of field:value pairs to filter by
            include_deleted: Whether to include soft-deleted entities

        Returns:
            Matching entity or None if not found
        """
        results = await self.find_by_fields(
            filters=filters,
            skip=0,
            limit=1,
            include_deleted=include_deleted
        )
        return results[0] if results else None

    def _build_query(self) -> Select:
        """
        Build base query for the model.

        Returns:
            Base SQLAlchemy select query
        """
        return select(self.model)
