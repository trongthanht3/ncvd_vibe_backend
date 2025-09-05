"""
Structured logging configuration with correlation ID support.

This module provides JSON structured logging with correlation ID middleware
for request tracing across the application.
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

import structlog
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


def add_correlation_id(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add correlation ID to log event.

    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Log event dictionary

    Returns:
        Event dictionary with correlation ID added
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def mask_sensitive_data(logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data in log events.

    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Log event dictionary

    Returns:
        Event dictionary with sensitive data masked
    """
    sensitive_keys = {
        "password", "token", "secret", "key", "authorization",
        "x-api-key", "client_secret", "access_token", "refresh_token"
    }

    def mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively mask sensitive keys in dictionary."""
        masked = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [mask_dict(item) if isinstance(
                    item, dict) else item for item in value]
            else:
                masked[key] = value
        return masked

    # Mask sensitive data in the event
    if "request" in event_dict and isinstance(event_dict["request"], dict):
        event_dict["request"] = mask_dict(event_dict["request"])

    if "response" in event_dict and isinstance(event_dict["response"], dict):
        event_dict["response"] = mask_dict(event_dict["response"])

    return event_dict


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up structlog with JSON formatting, correlation ID injection,
    and sensitive data masking.
    """
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
        mask_sensitive_data,
    ]

    # Add appropriate renderer based on format setting
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Set uvicorn loggers to use structured format
    uvicorn_loggers = ["uvicorn", "uvicorn.error", "uvicorn.access"]
    for logger_name in uvicorn_loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
