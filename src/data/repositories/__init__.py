"""
Repository pattern implementation for data access layer.

This module provides abstract base repositories and concrete implementations
for database operations with built-in security and CRUD abstraction.
"""

from .base import BaseRepository
from .user_repository import UserRepository
from .item_repository import ItemRepository

__all__ = ["BaseRepository", "UserRepository", "ItemRepository"]
