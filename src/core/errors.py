"""
Global error handling and custom exceptions.

This module provides centralized error handling for the FastAPI application,
including custom exceptions and error handlers with structured logging.
"""

from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .logging import get_logger

logger = get_logger(__name__)


class BaseAppError(Exception):
    """
    Base application error with structured error information.

    All custom exceptions should inherit from this class to ensure
    consistent error handling and logging.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        """
        Initialize base application error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error details
            status_code: HTTP status code
        """
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(BaseAppError):
    """Authentication-related errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "AUTHENTICATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(BaseAppError):
    """Authorization-related errors."""

    def __init__(
        self,
        message: str = "Access denied",
        error_code: str = "AUTHORIZATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(BaseAppError):
    """Resource not found errors."""

    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(BaseAppError):
    """Input validation errors."""

    def __init__(
        self,
        message: str = "Validation failed",
        error_code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class BusinessLogicError(BaseAppError):
    """Business logic errors."""

    def __init__(
        self,
        message: str = "Business logic error",
        error_code: str = "BUSINESS_LOGIC_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ExternalServiceError(BaseAppError):
    """External service integration errors."""

    def __init__(
        self,
        message: str = "External service error",
        error_code: str = "EXTERNAL_SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class DatabaseError(BaseAppError):
    """Database-related errors."""

    def __init__(
        self,
        message: str = "Database error",
        error_code: str = "DATABASE_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def create_error_response(
    error: Union[BaseAppError, HTTPException, Exception],
    request: Optional[Request] = None,
) -> JSONResponse:
    """
    Create standardized error response.

    Args:
        error: Error to convert to response
        request: FastAPI request object

    Returns:
        JSON error response
    """
    # Log the error with context
    error_context = {
        "error_type": error.__class__.__name__,
        "error_message": str(error),
    }

    if request:
        error_context.update({
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else None,
        })

    if isinstance(error, BaseAppError):
        # Custom application error
        logger.error("Application error occurred", **error_context,
                     error_code=error.error_code, details=error.details)

        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "message": error.message,
                    "code": error.error_code,
                    "details": error.details,
                },
                "success": False,
            },
        )

    elif isinstance(error, HTTPException):
        # FastAPI HTTP exception
        logger.error("HTTP error occurred", **error_context,
                     status_code=error.status_code)

        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "message": error.detail,
                    "code": "HTTP_ERROR",
                    "details": {},
                },
                "success": False,
            },
        )

    elif isinstance(error, ValidationError):
        # Pydantic validation error
        logger.error("Validation error occurred", **error_context,
                     validation_errors=error.errors())

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "message": "Validation failed",
                    "code": "VALIDATION_ERROR",
                    "details": {"validation_errors": error.errors()},
                },
                "success": False,
            },
        )

    else:
        # Unexpected error
        logger.error("Unexpected error occurred", **
                     error_context, exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "message": "Internal server error",
                    "code": "INTERNAL_ERROR",
                    "details": {},
                },
                "success": False,
            },
        )


async def base_app_error_handler(request: Request, exc: BaseAppError) -> JSONResponse:
    """
    Handler for custom application errors.

    Args:
        request: FastAPI request object
        exc: Application error

    Returns:
        JSON error response
    """
    return create_error_response(exc, request)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handler for HTTP exceptions.

    Args:
        request: FastAPI request object
        exc: HTTP exception

    Returns:
        JSON error response
    """
    return create_error_response(exc, request)


async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Handler for Pydantic validation errors.

    Args:
        request: FastAPI request object
        exc: Validation error

    Returns:
        JSON error response
    """
    return create_error_response(exc, request)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for unexpected exceptions.

    Args:
        request: FastAPI request object
        exc: Unexpected exception

    Returns:
        JSON error response
    """
    return create_error_response(exc, request)
