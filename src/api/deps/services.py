"""
Service layer dependencies for FastAPI endpoints.

This module provides dependency injection for application services,
ensuring proper service lifecycle and database session management.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.services.user_service import UserService
from ...application.services.item_service import ItemService
from ...application.services.document_service import DocumentService
from ...application.services.document_processing_service import DocumentProcessingService
from ...data.repositories.user_repository import UserRepository
from ...data.repositories.item_repository import ItemRepository
from ...data.repositories.document_repository import DocumentRepository
from ...data.repositories.sensitive_data_detection_repository import SensitiveDataDetectionRepository
from .database import get_db


async def get_user_repository(
    db: AsyncSession = Depends(get_db)
) -> UserRepository:
    """
    FastAPI dependency to provide UserRepository instance.

    Creates and returns a UserRepository with proper database session.

    Args:
        db: Database session

    Returns:
        UserRepository: User repository instance
    """
    return UserRepository(db)


async def get_item_repository(
    db: AsyncSession = Depends(get_db)
) -> ItemRepository:
    """
    FastAPI dependency to provide ItemRepository instance.

    Creates and returns an ItemRepository with proper database session.

    Args:
        db: Database session

    Returns:
        ItemRepository: Item repository instance
    """
    return ItemRepository(db)


async def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository)
) -> UserService:
    """
    FastAPI dependency to provide UserService instance.

    Creates and returns a UserService with injected dependencies.

    Args:
        user_repository: User repository for data access

    Returns:
        UserService: User service instance with dependencies
    """
    return UserService(user_repository)


async def get_item_service(
    item_repository: ItemRepository = Depends(get_item_repository)
) -> ItemService:
    """
    FastAPI dependency to provide ItemService instance.

    Creates and returns an ItemService with injected dependencies.

    Args:
        item_repository: Item repository for data access

    Returns:
        ItemService: Item service instance with dependencies
    """
    return ItemService(item_repository)


async def get_document_repository(
    db: AsyncSession = Depends(get_db)
) -> DocumentRepository:
    """
    FastAPI dependency to provide DocumentRepository instance.

    Creates and returns a DocumentRepository with proper database session.

    Args:
        db: Database session

    Returns:
        DocumentRepository: Document repository instance
    """
    return DocumentRepository(db)


async def get_sensitive_data_detection_repository(
    db: AsyncSession = Depends(get_db)
) -> SensitiveDataDetectionRepository:
    """
    FastAPI dependency to provide SensitiveDataDetectionRepository instance.

    Creates and returns a SensitiveDataDetectionRepository with proper database session.

    Args:
        db: Database session

    Returns:
        SensitiveDataDetectionRepository: Sensitive data detection repository instance
    """
    return SensitiveDataDetectionRepository(db)


async def get_document_processing_service() -> DocumentProcessingService:
    """
    FastAPI dependency to provide DocumentProcessingService instance.

    Creates and returns a DocumentProcessingService.

    Returns:
        DocumentProcessingService: Document processing service instance
    """
    return DocumentProcessingService()


async def get_document_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    sensitive_data_repository: SensitiveDataDetectionRepository = Depends(
        get_sensitive_data_detection_repository),
    processing_service: DocumentProcessingService = Depends(
        get_document_processing_service)
) -> DocumentService:
    """
    FastAPI dependency to provide DocumentService instance.

    Creates and returns a DocumentService with injected dependencies.

    Args:
        document_repository: Document repository for data access
        sensitive_data_repository: Sensitive data detection repository for data access
        processing_service: Document processing service for text extraction and scanning

    Returns:
        DocumentService: Document service instance with dependencies
    """
    return DocumentService(
        document_repository=document_repository,
        sensitive_data_repository=sensitive_data_repository,
        processing_service=processing_service
    )
