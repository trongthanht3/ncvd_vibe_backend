"""
Document management API endpoints.

This module provides REST API endpoints for document upload, scanning,
and management with proper authentication and access control.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Query
)
from fastapi.responses import JSONResponse
from ...core.auth import TokenData
from ..schemas.document_schemas import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentScanRequest,
    DocumentScanResponse,
    DocumentSearchFilters,
    PaginatedDocumentsResponse,
    DocumentContentResponse,
    SensitiveDataDetectionResponse,
    SensitiveDataReviewRequest,
    SensitiveDataReviewResponse,
    DocumentStatistics
)
from ..schemas.common_schemas import SuccessResponse, ErrorResponse
from ..deps.auth import get_current_user, get_current_user_id
from ..deps.services import get_document_service, get_sensitive_data_detection_repository
from ..deps.pagination import get_pagination_params, PaginationParams, create_pagination_metadata
from ...application.services.document_service import DocumentService
from ...data.repositories.sensitive_data_detection_repository import SensitiveDataDetectionRepository
from ...api.schemas.user_schemas import UserResponse
from ...core.exceptions import NotFoundError, ForbiddenError, ValidationError
from ...data.models.document import DocumentStatus, DocumentType
from ...data.models.sensitive_data_detection import SensitiveDataType, ConfidenceLevel

from ...core.auth import (
    get_current_active_user,
    get_current_user,
    exchange_code_for_token,
    get_keycloak_user_info,
    test_keycloak_connection,
    authenticate_user_direct,
    create_user_direct,
    TokenData,
    KeycloakUser,
    DirectLoginRequest,
    DirectAuthTokenData
)

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access forbidden"},
        404: {"model": ErrorResponse, "description": "Document not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    }
)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...,
                            description="Document file to upload (PDF or DOCX)"),
    current_user_id: TokenData = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentUploadResponse:
    """
    Upload a document for sensitive data scanning.

    Accepts PDF and DOCX files up to 50MB in size.
    The document will be queued for automatic scanning after upload.
    """
    try:
        # Validate file type
        if not file.content_type or file.content_type not in [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF and DOCX files are supported"
            )

        # Read file content
        file_content = await file.read()

        print("User ID:", current_user_id)

        # Upload document
        result = await document_service.upload_document(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            owner_id=current_user_id
        )

        return result

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("", response_model=PaginatedDocumentsResponse)
async def list_documents(
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service),
    search: Optional[str] = Query(
        None, description="Search in filename and content"),
    status: Optional[DocumentStatus] = Query(
        None, description="Filter by document status"),
    document_type: Optional[DocumentType] = Query(
        None, description="Filter by document type"),
    has_sensitive_data: Optional[bool] = Query(
        None, description="Filter by sensitive data presence")
) -> PaginatedDocumentsResponse:
    """
    List user's documents with filtering and pagination.

    Returns a paginated list of documents owned by the current user.
    """
    try:
        filters = DocumentSearchFilters(
            search_query=search,
            status=status,
            document_type=document_type,
            has_sensitive_data=has_sensitive_data
        )

        documents, total_count = await document_service.list_documents(
            requester_id=current_user_id,
            filters=filters,
            limit=pagination.limit,
            offset=pagination.offset
        )

        pagination_meta = create_pagination_metadata(
            total_items=total_count,
            page=pagination.page,
            limit=pagination.limit,
            base_url="/api/v1/documents"
        )

        return PaginatedDocumentsResponse(
            documents=documents,
            pagination=pagination_meta
        )

    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service),
    include_detections: bool = Query(
        True, description="Include sensitive data detections")
) -> DocumentResponse:
    """
    Get detailed information about a specific document.

    Returns document metadata, scanning status, and optionally
    sensitive data detections found during scanning.
    """
    try:
        document = await document_service.get_document_by_id(
            document_id=document_id,
            requester_id=current_user_id,
            include_detections=include_detections
        )
        return document

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to document"
        )


@router.post("/{document_id}/scan", response_model=DocumentScanResponse)
async def scan_document(
    document_id: UUID,
    scan_request: DocumentScanRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentScanResponse:
    """
    Trigger sensitive data scanning for a document.

    Starts the scanning process to detect sensitive information
    in the document content.
    """
    try:
        result = await document_service.scan_document(
            document_id=document_id,
            requester_id=current_user_id,
            force_rescan=scan_request.force_rescan
        )
        return result

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to document"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentContentResponse:
    """
    Get document content if safe to view.

    Returns the extracted text content only if the document
    has been scanned and contains no sensitive data.
    """
    try:
        content = await document_service.get_document_content(
            document_id=document_id,
            requester_id=current_user_id
        )

        return DocumentContentResponse(
            document_id=content["document_id"],
            filename=content["filename"],
            extracted_text=content["extracted_text"],
            page_count=content["page_count"],
            status=content["status"],
            has_sensitive_data=content["has_sensitive_data"],
            can_view_content=True,
            message="Document content is safe to view"
        )

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    except ForbiddenError as e:
        # Return partial response for forbidden content
        document = await document_service.get_document_by_id(
            document_id=document_id,
            requester_id=current_user_id,
            include_detections=False
        )

        return DocumentContentResponse(
            document_id=document.id,
            filename=document.filename,
            extracted_text=None,
            page_count=document.page_count,
            status=document.status,
            has_sensitive_data=document.has_sensitive_data,
            can_view_content=False,
            message=str(e)
        )


@router.delete("/{document_id}", response_model=SuccessResponse)
async def delete_document(
    document_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
) -> SuccessResponse:
    """
    Delete a document.

    Performs a soft delete of the document and its associated data.
    """
    try:
        await document_service.delete_document(
            document_id=document_id,
            requester_id=current_user_id
        )

        return SuccessResponse(message="Document deleted successfully")

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to document"
        )


@router.get("/statistics/overview", response_model=DocumentStatistics)
async def get_document_statistics(
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentStatistics:
    """
    Get document scanning statistics for the current user.

    Returns aggregated statistics about the user's documents
    and their scanning status.
    """
    try:
        stats = await document_service.get_document_statistics(current_user_id)

        return DocumentStatistics(
            by_status=stats["documents_by_status"],
            total_documents=stats["total_documents"],
            documents_with_sensitive_data=stats["documents_with_sensitive_data"],
            pending_scan=stats["pending_scan"],
            failed_scans=stats["failed_scans"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


# Sensitive Data Detection endpoints

@router.get("/{document_id}/detections", response_model=List[SensitiveDataDetectionResponse])
async def get_document_detections(
    document_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    document_service: DocumentService = Depends(get_document_service),
    sensitive_data_repo: SensitiveDataDetectionRepository = Depends(
        get_sensitive_data_detection_repository),
    data_type: Optional[SensitiveDataType] = Query(
        None, description="Filter by data type"),
    confidence_level: Optional[ConfidenceLevel] = Query(
        None, description="Filter by confidence level"),
    reviewed: Optional[bool] = Query(
        None, description="Filter by review status")
) -> List[SensitiveDataDetectionResponse]:
    """
    Get sensitive data detections for a document.

    Returns all sensitive data detections found in the specified document.
    """
    try:
        # Verify user has access to the document
        await document_service.get_document_by_id(
            document_id=document_id,
            requester_id=current_user_id,
            include_detections=False
        )

        # Get detections with filters
        detections = await sensitive_data_repo.find_by_document_id(
            document_id=document_id,
            data_type=data_type,
            confidence_level=confidence_level,
            reviewed=reviewed
        )

        return [
            SensitiveDataDetectionResponse.from_orm(detection)
            for detection in detections
        ]

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to document"
        )


@router.put("/detections/{detection_id}/review", response_model=SensitiveDataReviewResponse)
async def review_sensitive_data_detection(
    detection_id: UUID,
    review_request: SensitiveDataReviewRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    sensitive_data_repo: SensitiveDataDetectionRepository = Depends(
        get_sensitive_data_detection_repository),
    document_service: DocumentService = Depends(get_document_service)
) -> SensitiveDataReviewResponse:
    """
    Review a sensitive data detection.

    Mark a detection as reviewed and optionally as a false positive.
    Only the document owner can review detections.
    """
    try:
        # Get the detection to verify document ownership
        detection = await sensitive_data_repo.get_by_id(detection_id)
        if not detection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detection not found"
            )

        # Verify user has access to the document
        await document_service.get_document_by_id(
            document_id=detection.document_id,
            requester_id=current_user_id,
            include_detections=False
        )

        # Update the detection
        if review_request.false_positive:
            updated_detection = await sensitive_data_repo.mark_as_false_positive(
                detection_id=detection_id,
                notes=review_request.notes
            )
        else:
            updated_detection = await sensitive_data_repo.mark_as_reviewed(
                detection_id=detection_id,
                notes=review_request.notes
            )

        if not updated_detection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Detection not found"
            )

        message = "Detection marked as false positive" if review_request.false_positive else "Detection reviewed successfully"

        return SensitiveDataReviewResponse(
            id=updated_detection.id,
            reviewed=updated_detection.reviewed,
            false_positive=updated_detection.false_positive,
            review_notes=updated_detection.review_notes,
            message=message
        )

    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document or detection not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to document"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update detection review"
        )
