"""
API dependencies for dependency injection.

This module provides FastAPI dependencies for common operations like
database sessions, authentication, authorization, and service injection.
"""

from .database import get_db
from .auth import get_current_user, get_optional_current_user
from .services import get_user_service, get_item_service
from .pagination import get_pagination_params

__all__ = [
    "get_db",
    "get_current_user",
    "get_optional_current_user",
    "get_user_service",
    "get_item_service",
    "get_pagination_params"
]
