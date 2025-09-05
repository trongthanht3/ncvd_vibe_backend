"""
Custom exception classes for application error handling.

This module defines custom exceptions with proper HTTP status codes
and error messages for consistent API error responses.
"""

from typing import Any, Dict, Optional


class BaseAppException(Exception):
    """
    Base application exception with HTTP status code and details.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        """
        Initialize base exception.

        Args:
            message: Error message
            status_code: HTTP status code
            details: Additional error details
            error_code: Application-specific error code
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code


class ValidationError(BaseAppException):
    """
    Exception raised for validation errors.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "VALIDATION_ERROR"
    ):
        super().__init__(message, 400, details, error_code)


class NotFoundError(BaseAppException):
    """
    Exception raised when a resource is not found.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "NOT_FOUND"
    ):
        super().__init__(message, 404, details, error_code)


class ConflictError(BaseAppException):
    """
    Exception raised for resource conflicts.
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "CONFLICT"
    ):
        super().__init__(message, 409, details, error_code)


class ForbiddenError(BaseAppException):
    """
    Exception raised for authorization failures (IDOR protection).
    """

    def __init__(
        self,
        message: str = "Access forbidden",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "FORBIDDEN"
    ):
        super().__init__(message, 403, details, error_code)


class UnauthorizedError(BaseAppException):
    """
    Exception raised for authentication failures.
    """

    def __init__(
        self,
        message: str = "Authentication required",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "UNAUTHORIZED"
    ):
        super().__init__(message, 401, details, error_code)


class RateLimitError(BaseAppException):
    """
    Exception raised when rate limits are exceeded.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "RATE_LIMIT"
    ):
        super().__init__(message, 429, details, error_code)


class ServiceUnavailableError(BaseAppException):
    """
    Exception raised when external services are unavailable.
    """

    def __init__(
        self,
        message: str = "Service unavailable",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "SERVICE_UNAVAILABLE"
    ):
        super().__init__(message, 503, details, error_code)


class DatabaseError(BaseAppException):
    """
    Exception raised for database-related errors.
    """

    def __init__(
        self,
        message: str = "Database error",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "DATABASE_ERROR"
    ):
        super().__init__(message, 500, details, error_code)


class ExternalServiceError(BaseAppException):
    """
    Exception raised for external service integration errors.
    """

    def __init__(
        self,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "EXTERNAL_SERVICE_ERROR"
    ):
        super().__init__(message, 502, details, error_code)
