"""
Document schemas for API request/response validation.

This module defines Pydantic schemas for document-related API operations
including upload, scanning, and retrieval.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum

# Import enums from models
from ...data.models.document import DocumentStatus, DocumentType
from ...data.models.sensitive_data_detection import SensitiveDataType, ConfidenceLevel


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""
    document_id: UUID
    filename: str
    file_size: int
    document_type: DocumentType
    status: DocumentStatus
    message: str = "Document uploaded successfully and queued for scanning"

    class Config:
        from_attributes = True


class SensitiveDataDetectionResponse(BaseModel):
    """Response schema for sensitive data detection."""
    id: UUID
    data_type: SensitiveDataType
    masked_text: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    context: Optional[str] = None
    confidence_score: float
    confidence_level: ConfidenceLevel
    detection_pattern: Optional[str] = None
    ai_model_used: str
    reviewed: bool
    false_positive: bool
    review_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Confidence score must be between 0.0 and 1.0')
        return v


class DocumentResponse(BaseModel):
    """Response schema for document information."""
    id: UUID
    filename: str
    file_size: int
    file_size_mb: float
    content_type: str
    document_type: DocumentType
    status: DocumentStatus
    page_count: Optional[int] = None
    has_sensitive_data: bool
    scan_started_at: Optional[datetime] = None
    scan_completed_at: Optional[datetime] = None
    ai_model_used: Optional[str] = None
    error_message: Optional[str] = None
    owner_id: UUID
    owner_name: Optional[str] = None
    sensitive_data_count: int = 0
    sensitive_data_detections: List[SensitiveDataDetectionResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @validator('file_size_mb', pre=True)
    def calculate_file_size_mb(cls, v, values):
        if 'file_size' in values:
            return round(values['file_size'] / (1024 * 1024), 2)
        return v

    @validator('sensitive_data_count', pre=True)
    def count_sensitive_detections(cls, v, values):
        if 'sensitive_data_detections' in values:
            return len(values['sensitive_data_detections'])
        return v


class DocumentListResponse(BaseModel):
    """Response schema for document listing."""
    id: UUID
    filename: str
    file_size_mb: float
    document_type: DocumentType
    status: DocumentStatus
    has_sensitive_data: bool
    sensitive_data_count: int = 0
    scan_completed_at: Optional[datetime] = None
    owner_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSearchFilters(BaseModel):
    """Schema for document search filters."""
    search_query: Optional[str] = Field(
        None, description="Search in filename and content")
    status: Optional[DocumentStatus] = Field(
        None, description="Filter by document status")
    document_type: Optional[DocumentType] = Field(
        None, description="Filter by document type")
    has_sensitive_data: Optional[bool] = Field(
        None, description="Filter by sensitive data presence")
    owner_id: Optional[UUID] = Field(
        None, description="Filter by document owner")
    date_from: Optional[datetime] = Field(
        None, description="Filter documents created after this date")
    date_to: Optional[datetime] = Field(
        None, description="Filter documents created before this date")


class PaginatedDocumentsResponse(BaseModel):
    """Response schema for paginated document listing."""
    documents: List[DocumentListResponse]
    pagination: Dict[str, Any]


class DocumentScanRequest(BaseModel):
    """Request schema for triggering document scan."""
    force_rescan: bool = Field(
        False, description="Force rescan even if already scanned")


class DocumentScanResponse(BaseModel):
    """Response schema for document scan operation."""
    document_id: UUID
    status: DocumentStatus
    message: str
    scan_started_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SensitiveDataStatistics(BaseModel):
    """Schema for sensitive data statistics."""
    by_data_type: Dict[str, int]
    by_confidence_level: Dict[str, int]
    review_status: Dict[str, int]


class DocumentStatistics(BaseModel):
    """Schema for document statistics."""
    by_status: Dict[str, int]
    total_documents: int
    documents_with_sensitive_data: int
    pending_scan: int
    failed_scans: int


class SensitiveDataReviewRequest(BaseModel):
    """Request schema for reviewing sensitive data detection."""
    reviewed: bool = True
    false_positive: bool = False
    notes: Optional[str] = Field(
        None, max_length=1000, description="Review notes")

    @validator('false_positive')
    def validate_false_positive_reviewed(cls, v, values):
        if v and not values.get('reviewed', False):
            raise ValueError('Cannot mark as false positive without reviewing')
        return v


class SensitiveDataReviewResponse(BaseModel):
    """Response schema for sensitive data review."""
    id: UUID
    reviewed: bool
    false_positive: bool
    review_notes: Optional[str] = None
    message: str

    class Config:
        from_attributes = True


class DocumentContentResponse(BaseModel):
    """Response schema for document content retrieval."""
    document_id: UUID
    filename: str
    extracted_text: Optional[str] = None
    page_count: Optional[int] = None
    status: DocumentStatus
    has_sensitive_data: bool
    can_view_content: bool
    message: Optional[str] = None

    class Config:
        from_attributes = True

    @validator('can_view_content', pre=True)
    def determine_view_permission(cls, v, values):
        status = values.get('status')
        return status == DocumentStatus.READY_TO_VIEW


class DocumentProcessingMetadata(BaseModel):
    """Schema for document processing metadata."""
    pages_processed: Optional[int] = None
    chunks_created: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    ai_model_version: Optional[str] = None
    extraction_method: Optional[str] = None
    scan_rules_applied: Optional[List[str]] = None
    error_details: Optional[Dict[str, Any]] = None


class BulkDocumentOperation(BaseModel):
    """Schema for bulk document operations."""
    document_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    operation: str = Field(...,
                           description="Operation to perform (scan, delete, etc.)")
    force: bool = Field(
        False, description="Force operation even if not normally allowed")

    @validator('operation')
    def validate_operation(cls, v):
        allowed_operations = ['scan', 'delete', 'mark_reviewed']
        if v not in allowed_operations:
            raise ValueError(f'Operation must be one of: {allowed_operations}')
        return v


class BulkDocumentOperationResponse(BaseModel):
    """Response schema for bulk document operations."""
    total_requested: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = []
    message: str


class DocumentScanProgress(BaseModel):
    """Schema for document scan progress tracking."""
    document_id: UUID
    status: DocumentStatus
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0)
    current_step: str
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SensitiveDataPattern(BaseModel):
    """Schema for sensitive data detection patterns."""
    data_type: SensitiveDataType
    pattern_name: str
    pattern_description: str
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0)
    enabled: bool = True


class DocumentExportRequest(BaseModel):
    """Request schema for document export."""
    format: str = Field('json', description="Export format (json, csv, xlsx)")
    include_content: bool = Field(
        False, description="Include extracted text content")
    include_detections: bool = Field(
        True, description="Include sensitive data detections")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status_filter: Optional[List[DocumentStatus]] = None

    @validator('format')
    def validate_format(cls, v):
        allowed_formats = ['json', 'csv', 'xlsx']
        if v not in allowed_formats:
            raise ValueError(f'Format must be one of: {allowed_formats}')
        return v
