"""
Document repository for data access operations.

This module provides data access methods for Document entities
with proper filtering, searching, and ownership validation.
"""

from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.document import Document, DocumentStatus, DocumentType


class DocumentRepository(BaseRepository[Document, dict, dict]):
    """
    Repository for Document entity data access.

    Provides methods for creating, reading, updating, and deleting
    Document entities with proper access control.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(Document, db)
        self.db = db

    async def find_by_owner_id(
        self,
        owner_id: UUID,
        status: Optional[DocumentStatus] = None,
        document_type: Optional[DocumentType] = None,
        include_deleted: bool = False
    ) -> List[Document]:
        """
        Get all documents by owner.

        Args:
            owner_id: ID of the document owner
            status: Optional status filter
            document_type: Optional document type filter
            include_deleted: Whether to include soft-deleted documents

        Returns:
            List of documents belonging to the owner
        """
        query = select(self.model).where(
            self.model.owner_id == owner_id
        ).options(
            selectinload(self.model.sensitive_data_detections)
        )

        # Filter by status if provided
        if status:
            query = query.where(self.model.status == status)

        # Filter by document type if provided
        if document_type:
            query = query.where(self.model.document_type == document_type)

        # Handle soft-deleted documents
        if not include_deleted:
            query = query.where(self.model.deleted_at.is_(None))

        # Order by creation date (newest first)
        query = query.order_by(desc(self.model.created_at))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def find_scannable_documents(
        self,
        limit: int = 10
    ) -> List[Document]:
        """
        Get documents that are ready for scanning.

        Args:
            limit: Maximum number of documents to return

        Returns:
            List of documents ready for scanning
        """
        query = select(self.model).where(
            and_(
                self.model.status.in_([
                    DocumentStatus.UPLOADED,
                    DocumentStatus.FAILED
                ]),
                self.model.deleted_at.is_(None)
            )
        ).order_by(
            self.model.created_at
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def find_documents_by_status(
        self,
        status: DocumentStatus,
        owner_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Document], int]:
        """
        Get documents by status with pagination.

        Args:
            status: Document status to filter by
            owner_id: Optional owner filter
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            Tuple of (documents, total_count)
        """
        # Base query
        query = select(self.model).where(
            and_(
                self.model.status == status,
                self.model.deleted_at.is_(None)
            )
        ).options(
            selectinload(self.model.owner),
            selectinload(self.model.sensitive_data_detections)
        )

        # Count query
        count_query = select(func.count()).select_from(
            select(self.model.id).where(
                and_(
                    self.model.status == status,
                    self.model.deleted_at.is_(None)
                )
            ).subquery()
        )

        # Add owner filter if provided
        if owner_id:
            owner_filter = self.model.owner_id == owner_id
            query = query.where(owner_filter)
            count_query = count_query.where(owner_filter)

        # Apply pagination and ordering
        query = query.order_by(desc(self.model.created_at))
        query = query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()

        return documents, total_count

    async def search_documents(
        self,
        search_query: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        status: Optional[DocumentStatus] = None,
        document_type: Optional[DocumentType] = None,
        has_sensitive_data: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Document], int]:
        """
        Search documents with filters.

        Args:
            search_query: Text to search in filename and content
            owner_id: Optional owner filter
            status: Optional status filter
            document_type: Optional document type filter
            has_sensitive_data: Optional sensitive data filter
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            Tuple of (documents, total_count)
        """
        # Base query for non-deleted documents
        query = select(self.model).where(
            self.model.deleted_at.is_(None)
        ).options(
            selectinload(self.model.owner),
            selectinload(self.model.sensitive_data_detections)
        )

        # Count query
        count_query = select(func.count()).select_from(
            select(self.model.id).where(
                self.model.deleted_at.is_(None)
            ).subquery()
        )

        # Build filters
        filters = []

        if search_query:
            search_filter = or_(
                self.model.filename.ilike(f"%{search_query}%"),
                self.model.extracted_text.ilike(f"%{search_query}%")
            )
            filters.append(search_filter)

        if owner_id:
            filters.append(self.model.owner_id == owner_id)

        if status:
            filters.append(self.model.status == status)

        if document_type:
            filters.append(self.model.document_type == document_type)

        if has_sensitive_data is not None:
            filters.append(self.model.has_sensitive_data == has_sensitive_data)

        # Apply filters
        if filters:
            combined_filter = and_(*filters)
            query = query.where(combined_filter)
            count_query = count_query.where(combined_filter)

        # Apply pagination and ordering
        query = query.order_by(desc(self.model.created_at))
        query = query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()

        return documents, total_count

    async def get_by_id_with_detections(
        self,
        document_id: UUID
    ) -> Optional[Document]:
        """
        Get document by ID with all sensitive data detections loaded.

        Args:
            document_id: ID of the document

        Returns:
            Document with sensitive data detections or None
        """
        query = select(self.model).where(
            and_(
                self.model.id == document_id,
                self.model.deleted_at.is_(None)
            )
        ).options(
            selectinload(self.model.owner),
            selectinload(self.model.sensitive_data_detections)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_scan_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        has_sensitive_data: Optional[bool] = None,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        """
        Update document scanning status.

        Args:
            document_id: ID of the document
            status: New status
            has_sensitive_data: Whether sensitive data was found
            error_message: Error message if scan failed

        Returns:
            Updated document or None if not found
        """
        document = await self.get_by_id(document_id)
        if not document:
            return None

        document.status = status

        if has_sensitive_data is not None:
            document.has_sensitive_data = has_sensitive_data

        if error_message:
            document.error_message = error_message

        # Update scan completion time based on status
        if status in [DocumentStatus.COMPLETED, DocumentStatus.READY_TO_VIEW,
                      DocumentStatus.HAS_SENSITIVE_DATA, DocumentStatus.FAILED]:
            from datetime import datetime
            document.scan_completed_at = datetime.utcnow()
        elif status == DocumentStatus.PROCESSING:
            from datetime import datetime
            document.scan_started_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def get_scanning_statistics(
        self,
        owner_id: Optional[UUID] = None
    ) -> dict:
        """
        Get scanning statistics.

        Args:
            owner_id: Optional owner filter

        Returns:
            Dictionary with scanning statistics
        """
        query = select(
            self.model.status,
            func.count(self.model.id).label('count')
        ).where(
            self.model.deleted_at.is_(None)
        )

        if owner_id:
            query = query.where(self.model.owner_id == owner_id)

        query = query.group_by(self.model.status)

        result = await self.db.execute(query)
        stats = {}

        for row in result:
            stats[row.status.value] = row.count

        # Ensure all statuses are represented
        for status in DocumentStatus:
            if status.value not in stats:
                stats[status.value] = 0

        return stats
