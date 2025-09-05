# 3-Layer Architecture Guide

## Overview

This guide explains the new 3-layer architecture implemented in the Hakathon backend. The architecture follows Domain-Driven Design (DDD) principles and provides clear separation of concerns, IDOR protection, and comprehensive security features.

## Architecture Layers

```
src/
├── api/                    # Presentation Layer
│   ├── routers/           # FastAPI route handlers
│   ├── schemas/           # Pydantic models for request/response
│   └── deps/              # Dependency injection
├── application/           # Application Layer
│   └── services/          # Business logic and orchestration
├── data/                  # Data Layer
│   └── repositories/      # Data access with ORM abstraction
└── core/                  # Cross-cutting concerns
    ├── auth/              # Authentication & authorization
    ├── config/            # Configuration management
    └── exceptions/        # Custom exception hierarchy
```

### 1. Presentation Layer (`src/api/`)

**Purpose**: Handle HTTP requests, validation, and response formatting

#### Components:

- **Routers** (`src/api/routers/`): FastAPI route handlers
- **Schemas** (`src/api/schemas/`): Pydantic models for validation
- **Dependencies** (`src/api/deps/`): Dependency injection factories

#### Key Features:

- Request/response validation via Pydantic
- Automatic OpenAPI documentation
- Dependency injection for services and auth
- Standardized error handling
- Role-based access control

#### Example Router Structure:

```python
from fastapi import APIRouter, Depends, HTTPException
from ..schemas.user_schemas import UserResponse, UserCreate
from ..deps.auth import get_current_user
from ..deps.services import get_user_service

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    return current_user

@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    user_create: UserCreate,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    return await user_service.create_user(user_create)
```

### 2. Application Layer (`src/application/`)

**Purpose**: Implement business logic, orchestrate operations, and enforce security

#### Components:

- **Services** (`src/application/services/`): Business logic implementation

#### Key Features:

- IDOR (Insecure Direct Object Reference) protection
- Business rule enforcement
- Transaction management
- Audit logging
- Complex operation orchestration

#### Example Service Structure:

```python
from uuid import UUID
from ..data.repositories.user_repository import UserRepository
from ..core.exceptions import NotFoundError, ForbiddenError

class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def get_user_by_id(
        self,
        user_id: UUID,
        current_user_id: UUID
    ) -> UserResponse:
        # IDOR Protection: Check ownership or admin role
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        # Allow access to own profile or if admin
        if user.id != current_user_id and not self._is_admin(current_user_id):
            raise ForbiddenError("Access denied")

        return user
```

### 3. Data Layer (`src/data/`)

**Purpose**: Handle database operations with ORM abstraction

#### Components:

- **Repositories** (`src/data/repositories/`): Database access patterns

#### Key Features:

- Generic repository pattern with base operations
- Async SQLAlchemy integration
- Query optimization and caching
- Database-agnostic operations
- Bulk operation support

#### Example Repository Structure:

```python
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    def __init__(self, db: AsyncSession, model_class: type[T]):
        self.db = db
        self.model_class = model_class

    async def get_by_id(self, id: UUID) -> Optional[T]:
        result = await self.db.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()

    async def create(self, entity: T) -> T:
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity
```

## Security Features

### IDOR Protection

All services implement IDOR protection by default:

```python
async def get_item_by_id(
    self,
    item_id: UUID,
    requester_id: Optional[UUID] = None
) -> ItemResponse:
    item = await self.item_repository.get_by_id(item_id)
    if not item:
        raise NotFoundError("Item not found")

    # Public items are accessible to everyone
    if item.is_public:
        return item

    # Private items require ownership
    if not requester_id or item.owner_id != requester_id:
        raise ForbiddenError("Access denied to private item")

    return item
```

### Role-Based Access Control

Use dependency factories for role enforcement:

```python
from ..deps.auth import require_admin, require_role

@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: UserResponse = Depends(require_admin())
):
    # Only admins can access this endpoint
    pass

@router.get("/moderator-only")
async def moderator_endpoint(
    current_user: UserResponse = Depends(require_role("moderator"))
):
    # Only users with "moderator" role can access
    pass
```

### Authentication Flow

1. **Token Validation**: JWT tokens validated via Keycloak
2. **User Context**: Token subject mapped to user in database
3. **Permission Checks**: Role and ownership validation in services
4. **Audit Logging**: All operations logged with user context

## Dependency Injection

### Database Dependencies

```python
# src/api/deps/database.py
async def get_db() -> AsyncSession:
    async with get_session() as session:
        yield session
```

### Service Dependencies

```python
# src/api/deps/services.py
async def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository)
) -> UserService:
    return UserService(user_repository)

async def get_user_repository(
    db: AsyncSession = Depends(get_db)
) -> UserRepository:
    return UserRepository(db)
```

### Authentication Dependencies

```python
# src/api/deps/auth.py
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    # Validate JWT and return user
    pass

async def get_optional_current_user(...) -> Optional[UserResponse]:
    # Return None if not authenticated (for public endpoints)
    pass
```

## Schema Design

### Request/Response Models

```python
# src/api/schemas/user_schemas.py
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "user"

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

### Pagination and Search

```python
# src/api/schemas/common_schemas.py
class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    pagination: Dict[str, Any]

class PaginatedUsersResponse(PaginatedResponse[UserResponse]):
    users: List[UserResponse] = Field(alias="items")
```

## Error Handling

### Custom Exception Hierarchy

```python
# src/core/exceptions.py
class BaseAppException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundError(BaseAppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)

class ForbiddenError(BaseAppException):
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(message, 403)
```

### Error Handler Integration

```python
# In routers
try:
    result = await service.some_operation()
    return result
except NotFoundError:
    raise HTTPException(status_code=404, detail="Resource not found")
except ForbiddenError:
    raise HTTPException(status_code=403, detail="Access denied")
```

## Best Practices

### 1. Repository Pattern

- Always use repositories for database access
- Implement generic base repository for common operations
- Keep repositories focused on data access only

### 2. Service Layer

- Implement all business logic in services
- Always validate permissions and ownership
- Use transactions for multi-step operations
- Add comprehensive logging

### 3. API Layer

- Use Pydantic schemas for all input/output
- Implement proper error handling
- Document all endpoints with summaries and descriptions
- Use dependency injection for all external dependencies

### 4. Security

- Never trust user input - validate everything
- Always check ownership for resource access
- Implement role-based access control
- Log all sensitive operations

### 5. Testing

- Test each layer independently
- Mock external dependencies
- Test security controls thoroughly
- Include integration tests for complete flows

## Example Implementation

See the complete implementation examples in:

- **User Management**: `src/api/routers/users.py`
- **Item Management**: `src/api/routers/items.py`
- **User Service**: `src/application/services/user_service.py`
- **Item Service**: `src/application/services/item_service.py`
- **Repository Pattern**: `src/data/repositories/`

## Migration from Existing Code

1. **Move route handlers** from `src/routers/` to `src/api/routers/`
2. **Create service classes** for business logic in `src/application/services/`
3. **Implement repositories** for data access in `src/data/repositories/`
4. **Update dependencies** to use new dependency injection system
5. **Add IDOR protection** to all operations that access user data
6. **Implement proper error handling** with custom exceptions

This architecture provides a solid foundation for scalable, secure, and maintainable FastAPI applications.
