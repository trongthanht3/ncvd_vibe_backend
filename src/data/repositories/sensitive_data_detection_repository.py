"""
Sensitive Data Detection repository for data access operations.

This module provides data access methods for SensitiveDataDetection entities
with filtering and analysis capabilities.
"""

from typing import List, Optional, Tuple, Dict
from uuid import UUID
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.sensitive_data_detection import (
    SensitiveDataDetection,
    SensitiveDataType,
    ConfidenceLevel
)


class SensitiveDataDetectionRepository(BaseRepository[SensitiveDataDetection, dict, dict]):
    """
    Repository for SensitiveDataDetection entity data access.

    Provides methods for creating, reading, updating, and deleting
    SensitiveDataDetection entities with filtering and analysis.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(SensitiveDataDetection, db)

    async def find_by_document_id(
        self,
        document_id: UUID,
        data_type: Optional[SensitiveDataType] = None,
        confidence_level: Optional[ConfidenceLevel] = None,
        reviewed: Optional[bool] = None,
        false_positive: Optional[bool] = None
    ) -> List[SensitiveDataDetection]:
        """
        Get all detections for a specific document.

        Args:
            document_id: ID of the document
            data_type: Optional data type filter
            confidence_level: Optional confidence level filter
            reviewed: Optional reviewed status filter
            false_positive: Optional false positive filter

        Returns:
            List of sensitive data detections
        """
        query = select(self.model).where(
            self.model.document_id == document_id
        ).options(
            selectinload(self.model.document)
        )

        # Apply filters
        filters = []

        if data_type:
            filters.append(self.model.data_type == data_type)

        if confidence_level:
            filters.append(self.model.confidence_level == confidence_level)

        if reviewed is not None:
            filters.append(self.model.reviewed == reviewed)

        if false_positive is not None:
            filters.append(self.model.false_positive == false_positive)

        if filters:
            query = query.where(and_(*filters))

        # Order by confidence score (highest first)
        query = query.order_by(desc(self.model.confidence_score))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def find_high_confidence_detections(
        self,
        document_id: Optional[UUID] = None,
        data_type: Optional[SensitiveDataType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[SensitiveDataDetection], int]:
        """
        Get high confidence detections with pagination.

        Args:
            document_id: Optional document filter
            data_type: Optional data type filter
            limit: Maximum number of detections to return
            offset: Number of detections to skip

        Returns:
            Tuple of (detections, total_count)
        """
        # Base query for high confidence detections
        query = select(self.model).where(
            self.model.confidence_level == ConfidenceLevel.HIGH
        ).options(
            selectinload(self.model.document)
        )

        # Count query
        count_query = select(func.count()).select_from(
            select(self.model.id).where(
                self.model.confidence_level == ConfidenceLevel.HIGH
            ).subquery()
        )

        # Apply filters
        filters = []

        if document_id:
            filters.append(self.model.document_id == document_id)

        if data_type:
            filters.append(self.model.data_type == data_type)

        if filters:
            combined_filter = and_(*filters)
            query = query.where(combined_filter)
            count_query = count_query.where(combined_filter)

        # Apply pagination and ordering
        query = query.order_by(desc(self.model.confidence_score))
        query = query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(query)
        detections = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()

        return detections, total_count

    async def find_unreviewed_detections(
        self,
        data_type: Optional[SensitiveDataType] = None,
        confidence_level: Optional[ConfidenceLevel] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[SensitiveDataDetection], int]:
        """
        Get unreviewed detections with pagination.

        Args:
            data_type: Optional data type filter
            confidence_level: Optional confidence level filter
            limit: Maximum number of detections to return
            offset: Number of detections to skip

        Returns:
            Tuple of (detections, total_count)
        """
        # Base query for unreviewed, non-false-positive detections
        query = select(self.model).where(
            and_(
                self.model.reviewed == False,
                self.model.false_positive == False
            )
        ).options(
            selectinload(self.model.document)
        )

        # Count query
        count_query = select(func.count()).select_from(
            select(self.model.id).where(
                and_(
                    self.model.reviewed == False,
                    self.model.false_positive == False
                )
            ).subquery()
        )

        # Apply filters
        filters = []

        if data_type:
            filters.append(self.model.data_type == data_type)

        if confidence_level:
            filters.append(self.model.confidence_level == confidence_level)

        if filters:
            combined_filter = and_(*filters)
            query = query.where(combined_filter)
            count_query = count_query.where(combined_filter)

        # Apply pagination and ordering
        query = query.order_by(desc(self.model.confidence_score))
        query = query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(query)
        detections = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()

        return detections, total_count

    async def bulk_create_detections(
        self,
        detections: List[Dict]
    ) -> List[SensitiveDataDetection]:
        """
        Bulk create sensitive data detections.

        Args:
            detections: List of detection dictionaries

        Returns:
            List of created detection entities
        """
        detection_objects = []

        for detection_data in detections:
            detection = SensitiveDataDetection(
                document_id=detection_data['document_id'],
                data_type=detection_data['data_type'],
                detected_text=detection_data['detected_text'],
                masked_text=detection_data['masked_text'],
                page_number=detection_data.get('page_number'),
                chunk_index=detection_data.get('chunk_index'),
                context=detection_data.get('context'),
                confidence_score=detection_data['confidence_score'],
                confidence_level=SensitiveDataDetection.get_confidence_level(
                    detection_data['confidence_score']
                ),
                detection_pattern=detection_data.get('detection_pattern'),
                ai_model_used=detection_data['ai_model_used'],
                detection_metadata=detection_data.get('detection_metadata')
            )
            detection_objects.append(detection)

        # Add all detections to session
        for detection in detection_objects:
            self.db.add(detection)

        await self.db.commit()

        # Refresh all objects
        for detection in detection_objects:
            await self.db.refresh(detection)

        return detection_objects

    async def mark_as_reviewed(
        self,
        detection_id: UUID,
        notes: Optional[str] = None
    ) -> Optional[SensitiveDataDetection]:
        """
        Mark a detection as reviewed.

        Args:
            detection_id: ID of the detection
            notes: Optional review notes

        Returns:
            Updated detection or None if not found
        """
        detection = await self.get_by_id(detection_id)
        if not detection:
            return None

        detection.mark_as_reviewed(notes)
        await self.db.commit()
        await self.db.refresh(detection)
        return detection

    async def mark_as_false_positive(
        self,
        detection_id: UUID,
        notes: Optional[str] = None
    ) -> Optional[SensitiveDataDetection]:
        """
        Mark a detection as false positive.

        Args:
            detection_id: ID of the detection
            notes: Optional notes explaining why it's false positive

        Returns:
            Updated detection or None if not found
        """
        detection = await self.get_by_id(detection_id)
        if not detection:
            return None

        detection.mark_as_false_positive(notes)
        await self.db.commit()
        await self.db.refresh(detection)
        return detection

    async def get_detection_statistics(
        self,
        document_id: Optional[UUID] = None
    ) -> Dict:
        """
        Get detection statistics.

        Args:
            document_id: Optional document filter

        Returns:
            Dictionary with detection statistics
        """
        # Statistics by data type
        type_query = select(
            self.model.data_type,
            func.count(self.model.id).label('count')
        )

        if document_id:
            type_query = type_query.where(
                self.model.document_id == document_id)

        type_query = type_query.group_by(self.model.data_type)

        # Statistics by confidence level
        confidence_query = select(
            self.model.confidence_level,
            func.count(self.model.id).label('count')
        )

        if document_id:
            confidence_query = confidence_query.where(
                self.model.document_id == document_id
            )

        confidence_query = confidence_query.group_by(
            self.model.confidence_level)

        # Review status statistics
        review_query = select(
            func.count(self.model.id).label('total'),
            func.sum(
                func.case(
                    (self.model.reviewed == True, 1),
                    else_=0
                )
            ).label('reviewed'),
            func.sum(
                func.case(
                    (self.model.false_positive == True, 1),
                    else_=0
                )
            ).label('false_positives')
        )

        if document_id:
            review_query = review_query.where(
                self.model.document_id == document_id
            )

        # Execute queries
        type_result = await self.db.execute(type_query)
        confidence_result = await self.db.execute(confidence_query)
        review_result = await self.db.execute(review_query)

        # Process results
        type_stats = {}
        for row in type_result:
            type_stats[row.data_type.value] = row.count

        confidence_stats = {}
        for row in confidence_result:
            confidence_stats[row.confidence_level.value] = row.count

        review_row = review_result.first()
        review_stats = {
            'total': review_row.total or 0,
            'reviewed': review_row.reviewed or 0,
            'false_positives': review_row.false_positives or 0,
            'pending_review': (review_row.total or 0) - (review_row.reviewed or 0)
        }

        return {
            'by_data_type': type_stats,
            'by_confidence_level': confidence_stats,
            'review_status': review_stats
        }
