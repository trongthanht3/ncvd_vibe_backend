"""
Base repository implementation providing common CRUD operations.

This module defines the abstract base repository that all concrete repositories
should inherit from. It provides secure, ORM-based database operations with
built-in protection against SQL injection and common security vulnerabilities.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Generic type for model classes
ModelType = TypeVar("ModelType", bound=DeclarativeBase)

# Generic type for create/update schemas
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], ABC):
    """
    Abstract base repository for common CRUD operations.

    Provides secure database operations with built-in IDOR protection
    and SQL injection prevention through ORM-only queries.

    Args:
        model: SQLAlchemy model class
        session: Async database session
    """

    def __init__(self, model: type[ModelType], session: AsyncSession):
        """
        Initialize repository with model and session.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def get(self, id: Union[UUID, int]) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Record ID (UUID or int)

        Returns:
            Model instance or None if not found
        """
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner(
        self,
        id: Union[UUID, int],
        owner_id: Union[UUID, str]
    ) -> Optional[ModelType]:
        """
        Get a single record by ID with owner verification (IDOR protection).

        Args:
            id: Record ID
            owner_id: Owner ID to verify ownership

        Returns:
            Model instance or None if not found or not owned by user

        Raises:
            AttributeError: If model doesn't have owner_id field
        """
        if not hasattr(self.model, 'owner_id'):
            raise AttributeError(
                f"Model {self.model.__name__} must have 'owner_id' field for IDOR protection")

        stmt = select(self.model).where(
            and_(
                self.model.id == id,
                self.model.owner_id == owner_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        owner_id: Optional[Union[UUID, str]] = None
    ) -> List[ModelType]:
        """
        Get multiple records with pagination and optional owner filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return (max 1000)
            owner_id: Optional owner ID for filtering (IDOR protection)

        Returns:
            List of model instances
        """
        # Limit protection against large queries
        limit = min(limit, 1000)

        stmt = select(self.model).offset(skip).limit(limit)

        # Apply owner filter if provided and model supports it
        if owner_id is not None and hasattr(self.model, 'owner_id'):
            stmt = stmt.where(self.model.owner_id == owner_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj_in: CreateSchemaType, owner_id: Optional[Union[UUID, str]] = None) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: Creation schema with data
            owner_id: Optional owner ID to set (for IDOR protection)

        Returns:
            Created model instance
        """
        # If a SQLAlchemy model instance was passed in, use it directly
        # This avoids attempting `dict(obj_in)` on ORM objects which are not iterable
        if isinstance(obj_in, self.model):
            db_obj = obj_in
            # Set owner_id if provided and model supports it
            if owner_id is not None and hasattr(db_obj, 'owner_id'):
                setattr(db_obj, 'owner_id', owner_id)

            self.session.add(db_obj)
            await self.session.flush()
            await self.session.refresh(db_obj)
            return db_obj

        # Convert Pydantic model to dict, excluding unset fields, or accept dict-like input
        if hasattr(obj_in, 'model_dump'):
            obj_data = obj_in.model_dump(exclude_unset=True)
        else:
            obj_data = dict(obj_in)

        # Set owner_id if provided and model supports it
        if owner_id is not None and hasattr(self.model, 'owner_id'):
            obj_data['owner_id'] = owner_id

        db_obj = self.model(**obj_data)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        id: Union[UUID, int],
        obj_in: UpdateSchemaType,
        owner_id: Optional[Union[UUID, str]] = None
    ) -> Optional[ModelType]:
        """
        Update an existing record with IDOR protection.

        Args:
            id: Record ID to update
            obj_in: Update schema with new data
            owner_id: Owner ID for verification (IDOR protection)

        Returns:
            Updated model instance or None if not found/not owned
        """
        # Build base query
        stmt = select(self.model).where(self.model.id == id)

        # Apply owner filter if provided and model supports it
        if owner_id is not None and hasattr(self.model, 'owner_id'):
            stmt = stmt.where(self.model.owner_id == owner_id)

        result = await self.session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        # Convert update schema to dict, excluding unset fields
        if hasattr(obj_in, 'model_dump'):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = dict(obj_in)

        # Update fields
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(
        self,
        id: Union[UUID, int],
        owner_id: Optional[Union[UUID, str]] = None
    ) -> bool:
        """
        Delete a record with IDOR protection.

        Args:
            id: Record ID to delete
            owner_id: Owner ID for verification (IDOR protection)

        Returns:
            True if deleted, False if not found/not owned
        """
        # Build delete query
        stmt = delete(self.model).where(self.model.id == id)

        # Apply owner filter if provided and model supports it
        if owner_id is not None and hasattr(self.model, 'owner_id'):
            stmt = stmt.where(self.model.owner_id == owner_id)

        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def count(self, owner_id: Optional[Union[UUID, str]] = None) -> int:
        """
        Count records with optional owner filtering.

        Args:
            owner_id: Optional owner ID for filtering

        Returns:
            Number of records
        """
        stmt = select(func.count(self.model.id))

        # Apply owner filter if provided and model supports it
        if owner_id is not None and hasattr(self.model, 'owner_id'):
            stmt = stmt.where(self.model.owner_id == owner_id)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def exists(
        self,
        id: Union[UUID, int],
        owner_id: Optional[Union[UUID, str]] = None
    ) -> bool:
        """
        Check if a record exists with IDOR protection.

        Args:
            id: Record ID to check
            owner_id: Owner ID for verification (IDOR protection)

        Returns:
            True if exists and owned by user, False otherwise
        """
        stmt = select(func.count(self.model.id)).where(self.model.id == id)

        # Apply owner filter if provided and model supports it
        if owner_id is not None and hasattr(self.model, 'owner_id'):
            stmt = stmt.where(self.model.owner_id == owner_id)

        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[ModelType]:
        """
        Abstract method for email-based lookup.

        Concrete repositories should implement this method
        if the model supports email-based queries.

        Args:
            email: Email address to search for

        Returns:
            Model instance or None if not found
        """
        pass

    @abstractmethod
    async def search(self, query: str, owner_id: Optional[Union[UUID, str]] = None) -> List[ModelType]:
        """
        Abstract method for text-based search.

        Concrete repositories should implement this method
        based on their specific search requirements.

        Args:
            query: Search query string
            owner_id: Optional owner ID for filtering

        Returns:
            List of matching model instances
        """
        pass
