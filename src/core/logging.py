"""
Improved logging configuration with Loguru for better formatting and colors.

This module provides clean, colored logging with correlation ID support
for request tracing across the application.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from loguru import logger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None)


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.

    Returns:
        Current correlation ID or None if not set
    """
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID in context.

    Args:
        correlation_id: Correlation ID to set
    """
    correlation_id_var.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation ID for request tracing.

    This middleware:
    1. Extracts correlation ID from request headers or generates a new one
    2. Sets the correlation ID in context for the request duration
    3. Adds correlation ID to response headers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with correlation ID handling.

        Args:
            request: FastAPI request object
            call_next: Next middleware or route handler

        Returns:
            Response with correlation ID header added
        """
        # Get correlation ID from header or generate new one
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            request.headers.get("X-Request-ID", str(uuid.uuid4()))
        )

        # Set correlation ID in context
        set_correlation_id(correlation_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


class InterceptHandler(logging.Handler):
    """
    Handler to intercept standard logging and route it through Loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record through Loguru.

        Args:
            record: Standard library log record
        """
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # Get correlation ID for the log entry
        correlation_id = get_correlation_id() or "--------"

        logger.bind(correlation_id=correlation_id).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


def get_log_format() -> str:
    """
    Get the log format string based on environment.

    Returns:
        Loguru format string without extra newlines
    """
    if settings.app_env == "development":
        # Development format with colors and more details
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<yellow>ID:{extra[correlation_id]}</yellow> - "
            "<level>{message}</level>"
        )
    else:
        # Production format without colors, more structured
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "ID:{extra[correlation_id]} - "
            "{message}"
        )


def configure_logging() -> None:
    """
    Configure Loguru logging for the application.

    Sets up Loguru with clean formatting, colors (in development),
    and correlation ID injection.
    """
    # Remove default Loguru handler
    logger.remove()

    # Configure Loguru with custom formatting
    log_level = settings.log_level.upper()

    # Add console handler with custom formatting
    logger.add(
        sys.stdout,
        format=get_log_format(),
        level=log_level,
        colorize=settings.app_env == "development",
        backtrace=settings.app_debug,
        diagnose=settings.app_debug,
        enqueue=False,  # Set to True for multiprocessing safety if needed
    )

    # Add file handler for production (optional)
    if settings.app_env == "production":
        logger.add(
            "logs/app.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | ID:{extra[correlation_id]} - {message}",
            level=log_level,
            rotation="1 day",
            retention="30 days",
            compression="gz",
            serialize=False,
        )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Configure uvicorn loggers
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [InterceptHandler()]
        uvicorn_logger.setLevel(logging.INFO)

    # Configure other third-party loggers
    for logger_name in ["fastapi", "sqlalchemy.engine", "alembic"]:
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.handlers = [InterceptHandler()]
        third_party_logger.setLevel(logging.INFO)

    # Set SQLAlchemy to WARNING to reduce noise
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str):
    """
    Get a configured logger instance with correlation ID.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured Loguru logger with correlation ID bound
    """
    correlation_id = get_correlation_id() or "--------"
    return logger.bind(name=name, correlation_id=correlation_id)


# Convenience methods for common logging patterns
def log_request(request: Request, response: Response, duration: float) -> None:
    """
    Log HTTP request with correlation ID.

    Args:
        request: FastAPI request object
        response: FastAPI response object
        duration: Request processing duration in seconds
    """
    correlation_id = get_correlation_id() or "--------"
    logger.bind(correlation_id=correlation_id).info(
        f"{request.method} {request.url.path} {response.status_code} - {duration:.3f}s",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=duration,
        user_agent=request.headers.get("user-agent"),
    )


def log_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log error with context and correlation ID.

    Args:
        error: Exception to log
        context: Additional context information
    """
    correlation_id = get_correlation_id() or "--------"
    logger.bind(correlation_id=correlation_id).error(
        f"Error occurred: {str(error)}",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        exc_info=True,
    )
