"""
FastAPI application main entry point.

This module initializes the FastAPI application with all middleware,
error handlers, and routers configured according to the 3-tier architecture.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from .core.config import settings
from .core.cors import add_security_headers, configure_cors
from .core.errors import (
    BaseAppError,
    base_app_error_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from .core.logging import CorrelationIdMiddleware, configure_logging, get_logger

# Configure logging first
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown tasks for the FastAPI application.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup tasks
    logger.info("Starting up application", app_env=settings.app_env)

    # TODO: Initialize database connection pool
    # TODO: Initialize Milvus connection
    # TODO: Initialize JWKS cache

    logger.info("Application startup completed")

    yield

    # Shutdown tasks
    logger.info("Shutting down application")

    # TODO: Close database connections
    # TODO: Close Milvus connection
    # TODO: Cleanup JWKS cache

    logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="Hakathon Backend API",
        description="FastAPI backend with Keycloak OAuth2, PostgreSQL, and Milvus",
        version="0.1.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url="/redoc" if settings.app_env == "development" else None,
        openapi_url="/openapi.json" if settings.app_env == "development" else None,
        lifespan=lifespan,
    )

    # Configure CORS
    configure_cors(app)

    # Add security headers
    add_security_headers(app)

    # Add correlation ID middleware
    app.add_middleware(CorrelationIdMiddleware)

    # Configure error handlers
    app.add_exception_handler(BaseAppError, base_app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Add routers
    # TODO: Include API routers
    # from .api.routers import auth, users, items, search
    # app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    # app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    # app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
    # app.include_router(search.router, prefix="/api/v1/search", tags=["search"])

    # Add health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """
        Health check endpoint.

        Returns:
            Health status information
        """
        return {
            "status": "healthy",
            "environment": settings.app_env,
            "version": "0.1.0",
        }

    # Add root endpoint
    @app.get("/", tags=["root"])
    async def root() -> dict:
        """
        Root endpoint.

        Returns:
            API information
        """
        return {
            "message": "Hakathon Backend API",
            "version": "0.1.0",
            "docs_url": "/docs" if settings.app_env == "development" else None,
        }

    logger.info("FastAPI application configured",
                app_env=settings.app_env,
                debug=settings.app_debug)

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
