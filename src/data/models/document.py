"""
Document model for document scanning system.

This module defines the Document model that represents uploaded documents
and their scanning status for sensitive data detection.
"""

from typing import Optional
import uuid
from enum import Enum
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Integer, Enum as SQLEnum, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin

# Forward reference for User model to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User
    from .sensitive_data_detection import SensitiveDataDetection


class DocumentStatus(str, Enum):
    """Document processing status enumeration."""
    UPLOADED = "uploaded"  # Document uploaded, waiting for scan
    PROCESSING = "processing"  # Currently being scanned
    COMPLETED = "completed"  # Scan completed successfully
    FAILED = "failed"  # Scan failed
    READY_TO_VIEW = "ready_to_view"  # No sensitive data found, ready to view
    # Sensitive data found, requires review
    HAS_SENSITIVE_DATA = "has_sensitive_data"


class DocumentType(str, Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"


class Document(Base, SoftDeleteMixin):
    """
    Document model representing uploaded documents for scanning.

    Documents are scanned for sensitive data before being made available
    for viewing.
    """

    # Basic document information
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Original filename"
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Path to stored file"
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="File size in bytes"
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="MIME content type"
    )

    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType),
        nullable=False,
        doc="Document type (PDF or DOCX)"
    )

    # Owner relationship
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="ID of the user who uploaded this document"
    )

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.UPLOADED,
        nullable=False,
        index=True,
        doc="Current processing status"
    )

    # Content extraction
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Extracted text content in markdown format"
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Number of pages in document"
    )

    # Scanning results
    has_sensitive_data: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether sensitive data was detected"
    )

    scan_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When scanning started"
    )

    scan_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When scanning completed"
    )

    # Processing metadata
    processing_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Processing metadata and logs"
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Error message if processing failed"
    )

    # AI model information
    ai_model_used: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="AI model used for scanning"
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
        lazy="selectin"
    )

    sensitive_data_detections: Mapped[list["SensitiveDataDetection"]] = relationship(
        "SensitiveDataDetection",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        """
        String representation of the document.

        Returns:
            String representation showing filename and status
        """
        return f"<Document(filename='{self.filename}', status='{self.status}')>"

    @property
    def display_filename(self) -> str:
        """
        Get a display-friendly filename.

        Returns:
            Document filename, truncated if necessary
        """
        if len(self.filename) > 50:
            return f"{self.filename[:47]}..."
        return self.filename

    @property
    def is_scannable(self) -> bool:
        """
        Check if document can be scanned.

        Returns:
            True if document is in a state that allows scanning
        """
        return self.status in [DocumentStatus.UPLOADED, DocumentStatus.FAILED]

    @property
    def is_viewable(self) -> bool:
        """
        Check if document is viewable by users.

        Returns:
            True if document has been scanned and is safe to view
        """
        return self.status == DocumentStatus.READY_TO_VIEW

    @property
    def requires_review(self) -> bool:
        """
        Check if document requires admin review.

        Returns:
            True if document has sensitive data and requires review
        """
        return self.status == DocumentStatus.HAS_SENSITIVE_DATA

    def start_scanning(self) -> None:
        """
        Mark document as being scanned.
        """
        from datetime import datetime
        self.status = DocumentStatus.PROCESSING
        self.scan_started_at = datetime.utcnow()

    def complete_scanning(self, has_sensitive_data: bool) -> None:
        """
        Mark document scanning as completed.

        Args:
            has_sensitive_data: Whether sensitive data was found
        """
        from datetime import datetime
        self.has_sensitive_data = has_sensitive_data
        self.scan_completed_at = datetime.utcnow()

        if has_sensitive_data:
            self.status = DocumentStatus.HAS_SENSITIVE_DATA
        else:
            self.status = DocumentStatus.READY_TO_VIEW

    def fail_scanning(self, error_message: str) -> None:
        """
        Mark document scanning as failed.

        Args:
            error_message: Error message describing the failure
        """
        from datetime import datetime
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.scan_completed_at = datetime.utcnow()

    def update_processing_metadata(self, metadata: dict) -> None:
        """
        Update processing metadata.

        Args:
            metadata: Dictionary of metadata to update
        """
        if self.processing_metadata is None:
            self.processing_metadata = {}
        self.processing_metadata.update(metadata)

    def get_file_size_mb(self) -> float:
        """
        Get file size in megabytes.

        Returns:
            File size in MB rounded to 2 decimal places
        """
        return round(self.file_size / (1024 * 1024), 2)


# Create database indexes
Index('idx_document_filename', Document.filename)
Index('idx_document_owner_id', Document.owner_id)
Index('idx_document_status', Document.status)
Index('idx_document_document_type', Document.document_type)
Index('idx_document_has_sensitive_data', Document.has_sensitive_data)
Index('idx_document_created_at', Document.created_at)
Index('idx_document_scan_completed_at', Document.scan_completed_at)
Index('idx_document_deleted', Document.deleted_at)
