"""
CORS (Cross-Origin Resource Sharing) configuration.

This module provides secure CORS configuration for the FastAPI application,
with settings loaded from environment variables.
"""

from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings


def configure_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Determine allowed origins based on environment (ensure a list)
    allowed_origins = ["*", "http://localhost:4200",
                       "http://10.97.36.199:4200"]

    # In development, be more permissive
    if settings.app_env == "development":
        # Add common development origins if not already present
        dev_origins = ["http://localhost:4200",
                       "http://10.97.36.199:4200"]
        for origin in dev_origins:
            if origin not in allowed_origins:
                allowed_origins.append(origin)

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200",
                       "http://10.97.36.199:4200"],
        # allow_origins=["*"],
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Type",
            "Content-Language",
            "Authorization",
            "X-Correlation-ID",
            "X-Request-ID",
            "Cache-Control",
        ],
        expose_headers=[
            "X-Correlation-ID",
            "X-Request-ID",
        ],
        max_age=600,  # 10 minutes
    )


def add_security_headers(app: FastAPI) -> None:
    """
    Add security headers middleware to the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        """Middleware to add security headers to all responses."""

        async def dispatch(self, request: Request, call_next) -> Response:
            """
            Add security headers to response.

            Args:
                request: FastAPI request object
                call_next: Next middleware or route handler

            Returns:
                Response with security headers added
            """
            response = await call_next(request)

            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Add HSTS header for HTTPS in production
            if settings.app_env == "production" and request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains; preload"
                )

            return response

    app.add_middleware(SecurityHeadersMiddleware)
