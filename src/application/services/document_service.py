"""
Document service for business logic operations.

This module implements business logic for document management,
including upload, scanning, and sensitive data detection.
"""

from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID
import os
import aiofiles
from pathlib import Path
from datetime import datetime

from ...data.repositories.document_repository import DocumentRepository
from ...data.repositories.sensitive_data_detection_repository import SensitiveDataDetectionRepository
from ...data.models.document import Document, DocumentStatus, DocumentType
from ...data.models.sensitive_data_detection import SensitiveDataDetection
from ...api.schemas.document_schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentSearchFilters,
    DocumentUploadResponse,
    DocumentScanResponse,
    SensitiveDataDetectionResponse
)
from ...core.exceptions import NotFoundError, ForbiddenError, ValidationError
from ...core.logging import get_logger
from .document_processing_service import DocumentProcessingService

logger = get_logger(__name__)


class DocumentService:
    """
    Service for document management and scanning operations.

    Handles document upload, scanning coordination, and access control
    with proper IDOR protection.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        sensitive_data_repository: SensitiveDataDetectionRepository,
        processing_service: DocumentProcessingService,
        upload_directory: str = "uploads/documents"
    ):
        self.document_repository = document_repository
        self.sensitive_data_repository = sensitive_data_repository
        self.processing_service = processing_service
        self.upload_directory = Path(upload_directory)
        self.upload_directory.mkdir(parents=True, exist_ok=True)

    def _resolve_owner_id(self, owner_id) -> UUID:
        """
        Resolve various owner_id representations to a UUID.

        Accepts a UUID, a string UUID, a TokenData-like object with
        'user_id' attribute, or an object with 'id' attribute.
        """
        # Already a UUID
        if isinstance(owner_id, UUID):
            return owner_id

        # If it's a string, try to convert
        if isinstance(owner_id, str):
            try:
                return UUID(owner_id)
            except Exception:
                raise ValidationError("Invalid owner id format")

        # TokenData or similar objects (e.g., from auth dependency)
        if hasattr(owner_id, 'user_id'):
            candidate = getattr(owner_id, 'user_id')
            try:
                return UUID(str(candidate))
            except Exception:
                raise ValidationError("Invalid owner id in TokenData")

        # Generic object with 'id' attribute
        if hasattr(owner_id, 'id'):
            candidate = getattr(owner_id, 'id')
            try:
                return UUID(str(candidate))
            except Exception:
                raise ValidationError("Invalid owner id in object")

        raise ValidationError("Unable to resolve owner id to UUID")

    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        owner_id: UUID
    ) -> DocumentUploadResponse:
        """
        Upload and store a document for scanning.

        Args:
            file_content: Binary content of the uploaded file
            filename: Original filename
            content_type: MIME content type
            owner_id: ID of the user uploading the document

        Returns:
            Document upload response with document ID and status

        Raises:
            ValidationError: If file type is not supported or file is invalid
        """
        try:
            # Validate file type
            document_type = self._determine_document_type(
                filename, content_type)

            # Validate file size (max 50MB)
            max_size = 50 * 1024 * 1024  # 50MB
            if len(file_content) > max_size:
                raise ValidationError(
                    f"File size exceeds maximum allowed size of {max_size // (1024*1024)}MB")

            # Normalize owner id to UUID
            owner_uuid = self._resolve_owner_id(owner_id)

            # Generate unique file path
            file_path = self._generate_file_path(filename, owner_uuid)
            full_path = self.upload_directory / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Save file to disk
            async with aiofiles.open(full_path, 'wb') as f:
                await f.write(file_content)

            # Create document record
            document = Document(
                filename=filename,
                file_path=str(file_path),
                file_size=len(file_content),
                content_type=content_type,
                document_type=document_type,
                owner_id=owner_uuid,
                status=DocumentStatus.UPLOADED
            )

            created_document = await self.document_repository.create(document)

            logger.info(
                "Document uploaded successfully",
                document_id=str(created_document.id),
                filename=filename,
                owner_id=str(owner_id),
                file_size=len(file_content)
            )

            # TODO: Trigger background scanning task
            # await self._trigger_scanning_task(created_document.id)

            return DocumentUploadResponse(
                document_id=created_document.id,
                filename=created_document.filename,
                file_size=created_document.file_size,
                document_type=created_document.document_type,
                status=created_document.status
            )

        except Exception as e:
            logger.error(
                f"Failed to upload document: {e}", filename=filename, owner_id=str(owner_id))
            if isinstance(e, ValidationError):
                raise
            raise ValidationError("Failed to upload document")

    async def get_document_by_id(
        self,
        document_id: UUID,
        requester_id: UUID,
        include_detections: bool = True
    ) -> DocumentResponse:
        """
        Get document by ID with access control.

        Args:
            document_id: ID of the document
            requester_id: ID of the user requesting the document
            include_detections: Whether to include sensitive data detections

        Returns:
            Document response with details

        Raises:
            NotFoundError: If document doesn't exist
            ForbiddenError: If user doesn't have access to the document
        """
        # Normalize requester id
        requester_uuid = self._resolve_owner_id(requester_id)

        if include_detections:
            document = await self.document_repository.get_by_id_with_detections(document_id)
        else:
            document = await self.document_repository.get_by_id(document_id)

        if not document:
            raise NotFoundError("Document not found")

        # IDOR Protection: Check ownership
        if document.owner_id != requester_uuid:
            # TODO: Check if user has admin role for override
            raise ForbiddenError("Access denied to document")

        return self._convert_to_response(document, include_detections)

    async def list_documents(
        self,
        requester_id: UUID,
        filters: DocumentSearchFilters,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[DocumentListResponse], int]:
        """
        List documents with filtering and pagination.

        Args:
            requester_id: ID of the user requesting the list
            filters: Search and filter criteria
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            Tuple of (document list, total count)
        """
        # Normalize requester id
        requester_uuid = self._resolve_owner_id(requester_id)

        # Users can only see their own documents unless admin
        # TODO: Check admin role for viewing all documents
        if not filters.owner_id:
            filters.owner_id = requester_uuid
        else:
            # If a non-UUID owner_id was provided, try to normalize it
            try:
                filters.owner_id = self._resolve_owner_id(filters.owner_id)
            except ValidationError:
                pass

        if filters.owner_id != requester_uuid:
            # TODO: Check admin role
            raise ForbiddenError("Access denied to other users' documents")

        documents, total_count = await self.document_repository.search_documents(
            search_query=filters.search_query,
            owner_id=filters.owner_id,
            status=filters.status,
            document_type=filters.document_type,
            has_sensitive_data=filters.has_sensitive_data,
            limit=limit,
            offset=offset
        )

        document_responses = [
            self._convert_to_list_response(doc) for doc in documents
        ]

        return document_responses, total_count

    async def scan_document(
        self,
        document_id: UUID,
        requester_id: UUID,
        force_rescan: bool = False
    ) -> DocumentScanResponse:
        """
        Trigger document scanning for sensitive data.

        Args:
            document_id: ID of the document to scan
            requester_id: ID of the user requesting the scan
            force_rescan: Whether to force rescan even if already scanned

        Returns:
            Document scan response

        Raises:
            NotFoundError: If document doesn't exist
            ForbiddenError: If user doesn't have access to the document
            ValidationError: If document is not in a scannable state
        """
        # Normalize requester id
        requester_uuid = self._resolve_owner_id(requester_id)

        document = await self.document_repository.get_by_id(document_id)
        if not document:
            raise NotFoundError("Document not found")

        # IDOR Protection: Check ownership
        if document.owner_id != requester_uuid:
            raise ForbiddenError("Access denied to document")

        # Check if document can be scanned
        if not force_rescan and not document.is_scannable:
            if document.status == DocumentStatus.PROCESSING:
                raise ValidationError("Document is currently being processed")
            elif document.status in [DocumentStatus.READY_TO_VIEW, DocumentStatus.HAS_SENSITIVE_DATA]:
                raise ValidationError(
                    "Document has already been scanned. Use force_rescan=true to rescan.")

        # Update status to processing
        await self.document_repository.update_scan_status(
            document_id,
            DocumentStatus.PROCESSING
        )

        # Start scanning process
        scan_started_at = datetime.utcnow()

        try:
            # Perform the actual scanning
            await self._perform_document_scan(document)

            message = "Document scanning started successfully"
        except Exception as e:
            logger.error(
                f"Failed to start document scan: {e}", document_id=str(document_id))
            await self.document_repository.update_scan_status(
                document_id,
                DocumentStatus.FAILED,
                error_message=str(e)
            )
            raise ValidationError("Failed to start document scanning")

        return DocumentScanResponse(
            document_id=document_id,
            status=DocumentStatus.PROCESSING,
            message=message,
            scan_started_at=scan_started_at
        )

    async def get_document_content(
        self,
        document_id: UUID,
        requester_id: UUID
    ) -> Dict[str, Any]:
        """
        Get document content if safe to view.

        Args:
            document_id: ID of the document
            requester_id: ID of the user requesting content

        Returns:
            Document content and metadata

        Raises:
            NotFoundError: If document doesn't exist
            ForbiddenError: If user doesn't have access or document isn't safe to view
        """
        # Normalize requester id
        requester_uuid = self._resolve_owner_id(requester_id)

        document = await self.document_repository.get_by_id_with_detections(document_id)
        if not document:
            raise NotFoundError("Document not found")

        # IDOR Protection: Check ownership
        if document.owner_id != requester_uuid:
            raise ForbiddenError("Access denied to document")

        # Check if document is safe to view
        if not document.is_viewable:
            if document.status == DocumentStatus.PROCESSING:
                raise ForbiddenError("Document is still being processed")
            elif document.status == DocumentStatus.HAS_SENSITIVE_DATA:
                raise ForbiddenError(
                    "Document contains sensitive data and requires admin review")
            elif document.status == DocumentStatus.FAILED:
                raise ForbiddenError("Document processing failed")
            else:
                raise ForbiddenError("Document is not ready for viewing")

        return {
            "document_id": document.id,
            "filename": document.filename,
            "extracted_text": document.extracted_text,
            "page_count": document.page_count,
            "status": document.status,
            "has_sensitive_data": document.has_sensitive_data
        }

    async def delete_document(
        self,
        document_id: UUID,
        requester_id: UUID
    ) -> None:
        """
        Delete a document (soft delete).

        Args:
            document_id: ID of the document to delete
            requester_id: ID of the user requesting deletion

        Raises:
            NotFoundError: If document doesn't exist
            ForbiddenError: If user doesn't have access to the document
        """
        # Normalize requester id
        requester_uuid = self._resolve_owner_id(requester_id)

        document = await self.document_repository.get_by_id(document_id)
        if not document:
            raise NotFoundError("Document not found")

        # IDOR Protection: Check ownership
        if document.owner_id != requester_uuid:
            raise ForbiddenError("Access denied to document")

        # Soft delete the document
        await self.document_repository.soft_delete(document_id)

        # TODO: Schedule physical file deletion
        # await self._schedule_file_cleanup(document.file_path)

        logger.info(
            "Document deleted",
            document_id=str(document_id),
            requester_id=str(requester_id)
        )

    async def get_document_statistics(
        self,
        requester_id: UUID
    ) -> Dict[str, Any]:
        """
        Get document statistics for the user.

        Args:
            requester_id: ID of the user requesting statistics

        Returns:
            Document statistics
        """
        # Normalize requester id
        requester_uuid = self._resolve_owner_id(requester_id)

        # Get document statistics
        doc_stats = await self.document_repository.get_scanning_statistics(requester_uuid)

        # Get sensitive data statistics for user's documents
        # This would require a method to get user's document IDs first
        user_documents = await self.document_repository.find_by_owner_id(requester_uuid)

        total_sensitive_detections = 0
        for doc in user_documents:
            if doc.has_sensitive_data:
                detections = await self.sensitive_data_repository.find_by_document_id(doc.id)
                total_sensitive_detections += len(detections)

        return {
            "documents_by_status": doc_stats,
            "total_documents": sum(doc_stats.values()),
            "documents_with_sensitive_data": doc_stats.get("has_sensitive_data", 0),
            "total_sensitive_detections": total_sensitive_detections,
            "pending_scan": doc_stats.get("uploaded", 0),
            "failed_scans": doc_stats.get("failed", 0)
        }

    # Private helper methods

    def _determine_document_type(self, filename: str, content_type: str) -> DocumentType:
        """
        Determine document type from filename and content type.

        Args:
            filename: Original filename
            content_type: MIME content type

        Returns:
            DocumentType enum value

        Raises:
            ValidationError: If document type is not supported
        """
        filename_lower = filename.lower()

        if filename_lower.endswith('.pdf') or content_type == 'application/pdf':
            return DocumentType.PDF
        elif (filename_lower.endswith('.docx') or
              content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'):
            return DocumentType.DOCX
        else:
            raise ValidationError(
                "Unsupported document type. Only PDF and DOCX files are supported.")

    def _generate_file_path(self, filename: str, owner_id: UUID) -> str:
        """
        Generate unique file path for storage.

        Args:
            filename: Original filename
            owner_id: Owner user ID

        Returns:
            Unique file path
        """
        from uuid import uuid4
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        file_extension = Path(filename).suffix
        unique_filename = f"{timestamp}_{uuid4().hex[:8]}{file_extension}"
        return f"{owner_id}/{unique_filename}"

    async def _perform_document_scan(self, document: Document) -> None:
        """
        Perform the actual document scanning.

        Args:
            document: Document to scan
        """
        try:
            # Extract text from document
            extracted_text = await self.processing_service.extract_text_from_document(
                document.file_path,
                document.document_type
            )

            # Update document with extracted text
            document.extracted_text = extracted_text
            document.page_count = await self.processing_service.get_page_count(
                document.file_path,
                document.document_type
            )

            # Scan for sensitive data
            detections = await self.processing_service.scan_for_sensitive_data(
                extracted_text,
                document.id
            )

            # Save detections if any found
            has_sensitive_data = len(detections) > 0
            if has_sensitive_data:
                await self.sensitive_data_repository.bulk_create_detections(detections)

            # Update document status
            await self.document_repository.update_scan_status(
                document.id,
                DocumentStatus.HAS_SENSITIVE_DATA if has_sensitive_data else DocumentStatus.READY_TO_VIEW,
                has_sensitive_data=has_sensitive_data
            )

            logger.info(
                "Document scan completed",
                document_id=str(document.id),
                has_sensitive_data=has_sensitive_data,
                detections_count=len(detections)
            )

        except Exception as e:
            logger.error(
                f"Document scan failed: {e}", document_id=str(document.id))
            await self.document_repository.update_scan_status(
                document.id,
                DocumentStatus.FAILED,
                error_message=str(e)
            )
            raise

    def _convert_to_response(self, document: Document, include_detections: bool = True) -> DocumentResponse:
        """
        Convert Document model to DocumentResponse.

        Args:
            document: Document model instance
            include_detections: Whether to include sensitive data detections

        Returns:
            DocumentResponse schema
        """
        sensitive_detections = []
        if include_detections and document.sensitive_data_detections:
            sensitive_detections = [
                SensitiveDataDetectionResponse.from_orm(detection)
                for detection in document.sensitive_data_detections
            ]

        return DocumentResponse(
            id=document.id,
            filename=document.filename,
            file_size=document.file_size,
            file_size_mb=document.get_file_size_mb(),
            content_type=document.content_type,
            document_type=document.document_type,
            status=document.status,
            page_count=document.page_count,
            has_sensitive_data=document.has_sensitive_data,
            scan_started_at=document.scan_started_at,
            scan_completed_at=document.scan_completed_at,
            ai_model_used=document.ai_model_used,
            error_message=document.error_message,
            owner_id=document.owner_id,
            owner_name=document.owner.full_name if document.owner else None,
            sensitive_data_count=len(sensitive_detections),
            sensitive_data_detections=sensitive_detections,
            created_at=document.created_at,
            updated_at=document.updated_at
        )

    def _convert_to_list_response(self, document: Document) -> DocumentListResponse:
        """
        Convert Document model to DocumentListResponse.

        Args:
            document: Document model instance

        Returns:
            DocumentListResponse schema
        """
        return DocumentListResponse(
            id=document.id,
            filename=document.filename,
            file_size_mb=document.get_file_size_mb(),
            document_type=document.document_type,
            status=document.status,
            has_sensitive_data=document.has_sensitive_data,
            sensitive_data_count=len(
                document.sensitive_data_detections) if document.sensitive_data_detections else 0,
            scan_completed_at=document.scan_completed_at,
            owner_name=document.owner.full_name if document.owner else None,
            created_at=document.created_at
        )
