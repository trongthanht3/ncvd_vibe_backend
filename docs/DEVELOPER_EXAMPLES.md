# Developer Examples - 3-Layer Architecture

This document provides step-by-step examples for implementing new features using the 3-layer architecture.

## Table of Contents

1. [Creating a New Entity (Blog Posts)](#creating-a-new-entity-blog-posts)
2. [Adding Search Functionality](#adding-search-functionality)
3. [Implementing File Upload](#implementing-file-upload)
4. [Adding Audit Logging](#adding-audit-logging)
5. [Complex Business Logic Example](#complex-business-logic-example)

## Creating a New Entity (Blog Posts)

Let's walk through creating a complete blog post feature from scratch.

### Step 1: Define the Database Model

```python
# src/data/models/blog_post.py
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .base import BaseModel

class BlogPost(BaseModel):
    __tablename__ = "blog_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    excerpt = Column(String(500))
    is_published = Column(Boolean, default=False, index=True)
    publish_date = Column(DateTime(timezone=True), nullable=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    category = Column(String(100), index=True)
    tags = Column(String(500))  # JSON array as string
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    author = relationship("User", back_populates="blog_posts")
```

### Step 2: Create the Repository

```python
# src/data/repositories/blog_post_repository.py
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.blog_post import BlogPost

class BlogPostRepository(BaseRepository[BlogPost]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, BlogPost)

    async def find_by_author_id(
        self,
        author_id: UUID,
        include_unpublished: bool = False
    ) -> List[BlogPost]:
        """Get all blog posts by author."""
        query = select(self.model_class).where(
            self.model_class.author_id == author_id
        )

        if not include_unpublished:
            query = query.where(self.model_class.is_published == True)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def find_published(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[BlogPost], int]:
        """Search published blog posts with filters."""

        # Base query for published posts
        query = select(self.model_class).where(
            self.model_class.is_published == True
        ).options(selectinload(self.model_class.author))

        # Count query for pagination
        count_query = select(func.count()).select_from(
            select(self.model_class.id).where(
                self.model_class.is_published == True
            ).subquery()
        )

        # Apply filters
        filters = []

        if category:
            category_filter = self.model_class.category.ilike(f"%{category}%")
            filters.append(category_filter)

        if tag:
            tag_filter = self.model_class.tags.ilike(f"%{tag}%")
            filters.append(tag_filter)

        if search_query:
            search_filter = or_(
                self.model_class.title.ilike(f"%{search_query}%"),
                self.model_class.content.ilike(f"%{search_query}%"),
                self.model_class.excerpt.ilike(f"%{search_query}%")
            )
            filters.append(search_filter)

        if filters:
            combined_filter = and_(*filters)
            query = query.where(combined_filter)
            count_query = count_query.where(combined_filter)

        # Apply pagination and ordering
        query = query.order_by(desc(self.model_class.publish_date))
        query = query.offset(offset).limit(limit)

        # Execute queries
        result = await self.db.execute(query)
        posts = result.scalars().all()

        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()

        return posts, total_count

    async def increment_view_count(self, post_id: UUID) -> bool:
        """Increment view count for a blog post."""
        query = select(self.model_class).where(
            self.model_class.id == post_id
        )
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if post:
            post.view_count += 1
            await self.db.commit()
            return True
        return False
```

### Step 3: Create Pydantic Schemas

```python
# src/api/schemas/blog_post_schemas.py
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator

class BlogPostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    is_published: bool = False

class BlogPostCreate(BlogPostBase):
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v

class BlogPostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = None

class BlogPostResponse(BlogPostBase):
    id: UUID
    author_id: UUID
    author_name: Optional[str] = None
    publish_date: Optional[datetime]
    view_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaginatedBlogPostsResponse(BaseModel):
    posts: List[BlogPostResponse]
    pagination: dict

class BlogPostSearchFilters(BaseModel):
    category: Optional[str] = None
    tag: Optional[str] = None
    search_query: Optional[str] = None
    author_id: Optional[UUID] = None
```

### Step 4: Implement the Service Layer

```python
# src/application/services/blog_post_service.py
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from ...data.repositories.blog_post_repository import BlogPostRepository
from ...api.schemas.blog_post_schemas import (
    BlogPostCreate,
    BlogPostUpdate,
    BlogPostResponse,
    BlogPostSearchFilters
)
from ...core.exceptions import NotFoundError, ForbiddenError, ValidationError
from ...core.logging import get_logger

logger = get_logger(__name__)

class BlogPostService:
    def __init__(self, blog_post_repository: BlogPostRepository):
        self.blog_post_repository = blog_post_repository

    async def create_blog_post(
        self,
        post_data: BlogPostCreate,
        author_id: UUID
    ) -> BlogPostResponse:
        """Create a new blog post."""
        try:
            # Create blog post model
            blog_post = BlogPost(
                title=post_data.title,
                content=post_data.content,
                excerpt=post_data.excerpt or post_data.content[:500],
                category=post_data.category,
                tags=",".join(post_data.tags) if post_data.tags else None,
                is_published=post_data.is_published,
                author_id=author_id,
                publish_date=datetime.utcnow() if post_data.is_published else None
            )

            # Save to database
            created_post = await self.blog_post_repository.create(blog_post)

            logger.info(
                "Blog post created",
                post_id=str(created_post.id),
                author_id=str(author_id),
                title=created_post.title
            )

            return BlogPostResponse.from_orm(created_post)

        except Exception as e:
            logger.error(f"Failed to create blog post: {e}")
            raise ValidationError("Failed to create blog post")

    async def get_blog_post_by_id(
        self,
        post_id: UUID,
        requester_id: Optional[UUID] = None,
        increment_views: bool = True
    ) -> BlogPostResponse:
        """Get blog post by ID with access control."""

        post = await self.blog_post_repository.get_by_id(post_id)
        if not post:
            raise NotFoundError("Blog post not found")

        # Published posts are accessible to everyone
        if post.is_published:
            if increment_views:
                await self.blog_post_repository.increment_view_count(post_id)
            return BlogPostResponse.from_orm(post)

        # Unpublished posts only accessible to author
        if not requester_id or post.author_id != requester_id:
            raise ForbiddenError("Access denied to unpublished post")

        return BlogPostResponse.from_orm(post)

    async def update_blog_post(
        self,
        post_id: UUID,
        post_update: BlogPostUpdate,
        author_id: UUID
    ) -> BlogPostResponse:
        """Update blog post with ownership verification."""

        post = await self.blog_post_repository.get_by_id(post_id)
        if not post:
            raise NotFoundError("Blog post not found")

        # Verify ownership
        if post.author_id != author_id:
            raise ForbiddenError("Access denied - not post author")

        # Update fields
        update_data = post_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            if field == 'tags' and value:
                setattr(post, field, ",".join(value))
            elif field == 'is_published' and value and not post.is_published:
                # Set publish date when publishing for first time
                setattr(post, field, value)
                setattr(post, 'publish_date', datetime.utcnow())
            else:
                setattr(post, field, value)

        updated_post = await self.blog_post_repository.update(post)

        logger.info(
            "Blog post updated",
            post_id=str(post_id),
            author_id=str(author_id),
            updated_fields=list(update_data.keys())
        )

        return BlogPostResponse.from_orm(updated_post)

    async def delete_blog_post(self, post_id: UUID, author_id: UUID) -> None:
        """Delete blog post with ownership verification."""

        post = await self.blog_post_repository.get_by_id(post_id)
        if not post:
            raise NotFoundError("Blog post not found")

        # Verify ownership
        if post.author_id != author_id:
            raise ForbiddenError("Access denied - not post author")

        await self.blog_post_repository.delete(post_id)

        logger.info(
            "Blog post deleted",
            post_id=str(post_id),
            author_id=str(author_id)
        )

    async def search_blog_posts(
        self,
        filters: BlogPostSearchFilters,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[BlogPostResponse], int]:
        """Search published blog posts."""

        posts, total_count = await self.blog_post_repository.find_published(
            category=filters.category,
            tag=filters.tag,
            search_query=filters.search_query,
            limit=limit,
            offset=offset
        )

        post_responses = [BlogPostResponse.from_orm(post) for post in posts]
        return post_responses, total_count

    async def get_user_blog_posts(
        self,
        author_id: UUID,
        requester_id: UUID,
        include_unpublished: bool = False
    ) -> List[BlogPostResponse]:
        """Get blog posts by user with access control."""

        # Users can see all their own posts, others only see published
        if author_id == requester_id:
            posts = await self.blog_post_repository.find_by_author_id(
                author_id,
                include_unpublished=True
            )
        else:
            posts = await self.blog_post_repository.find_by_author_id(
                author_id,
                include_unpublished=False
            )

        return [BlogPostResponse.from_orm(post) for post in posts]
```

### Step 5: Create API Dependencies

```python
# src/api/deps/services.py (add to existing file)
async def get_blog_post_repository(
    db: AsyncSession = Depends(get_db)
) -> BlogPostRepository:
    return BlogPostRepository(db)

async def get_blog_post_service(
    blog_post_repository: BlogPostRepository = Depends(get_blog_post_repository)
) -> BlogPostService:
    return BlogPostService(blog_post_repository)
```

### Step 6: Create the API Router

```python
# src/api/routers/blog_posts.py
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from ..schemas.blog_post_schemas import (
    BlogPostResponse,
    BlogPostCreate,
    BlogPostUpdate,
    PaginatedBlogPostsResponse,
    BlogPostSearchFilters
)
from ..schemas.common_schemas import SuccessResponse, ErrorResponse
from ..deps.auth import get_current_user, get_optional_current_user, get_current_user_id
from ..deps.services import get_blog_post_service
from ..deps.pagination import get_pagination_params, PaginationParams, create_pagination_metadata
from ...application.services.blog_post_service import BlogPostService
from ...api.schemas.user_schemas import UserResponse
from ...core.exceptions import NotFoundError, ForbiddenError, ValidationError

router = APIRouter(
    prefix="/blog-posts",
    tags=["blog-posts"],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access forbidden"},
        404: {"model": ErrorResponse, "description": "Blog post not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    }
)

@router.get("", response_model=PaginatedBlogPostsResponse)
async def list_blog_posts(
    pagination: PaginationParams = Depends(get_pagination_params),
    blog_post_service: BlogPostService = Depends(get_blog_post_service),
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in title and content")
) -> PaginatedBlogPostsResponse:
    """List published blog posts with search and filtering."""

    try:
        filters = BlogPostSearchFilters(
            category=category,
            tag=tag,
            search_query=search
        )

        posts, total_count = await blog_post_service.search_blog_posts(
            filters=filters,
            limit=pagination.limit,
            offset=pagination.offset
        )

        pagination_meta = create_pagination_metadata(
            total_items=total_count,
            page=pagination.page,
            limit=pagination.limit,
            base_url="/api/v1/blog-posts"
        )

        return PaginatedBlogPostsResponse(
            posts=posts,
            pagination=pagination_meta
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.post("", response_model=BlogPostResponse, status_code=status.HTTP_201_CREATED)
async def create_blog_post(
    post_create: BlogPostCreate,
    current_user_id: UUID = Depends(get_current_user_id),
    blog_post_service: BlogPostService = Depends(get_blog_post_service)
) -> BlogPostResponse:
    """Create a new blog post."""

    try:
        new_post = await blog_post_service.create_blog_post(
            post_create,
            author_id=current_user_id
        )
        return new_post
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.get("/{post_id}", response_model=BlogPostResponse)
async def get_blog_post(
    post_id: UUID,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    blog_post_service: BlogPostService = Depends(get_blog_post_service)
) -> BlogPostResponse:
    """Get a blog post by ID."""

    try:
        user_id = current_user.id if current_user else None
        post = await blog_post_service.get_blog_post_by_id(
            post_id,
            requester_id=user_id
        )
        return post
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to unpublished post"
        )

@router.put("/{post_id}", response_model=BlogPostResponse)
async def update_blog_post(
    post_id: UUID,
    post_update: BlogPostUpdate,
    current_user_id: UUID = Depends(get_current_user_id),
    blog_post_service: BlogPostService = Depends(get_blog_post_service)
) -> BlogPostResponse:
    """Update a blog post."""

    try:
        updated_post = await blog_post_service.update_blog_post(
            post_id,
            post_update,
            author_id=current_user_id
        )
        return updated_post
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - not post author"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.delete("/{post_id}", response_model=SuccessResponse)
async def delete_blog_post(
    post_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    blog_post_service: BlogPostService = Depends(get_blog_post_service)
) -> SuccessResponse:
    """Delete a blog post."""

    try:
        await blog_post_service.delete_blog_post(post_id, author_id=current_user_id)
        return SuccessResponse(message="Blog post deleted successfully")
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog post not found"
        )
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied - not post author"
        )

@router.get("/users/{user_id}/posts", response_model=List[BlogPostResponse])
async def get_user_blog_posts(
    user_id: UUID,
    current_user: Optional[UserResponse] = Depends(get_optional_current_user),
    blog_post_service: BlogPostService = Depends(get_blog_post_service),
    include_unpublished: bool = Query(False, description="Include unpublished posts (author only)")
) -> List[BlogPostResponse]:
    """Get blog posts by a specific user."""

    try:
        requester_id = current_user.id if current_user else None
        posts = await blog_post_service.get_user_blog_posts(
            author_id=user_id,
            requester_id=requester_id,
            include_unpublished=include_unpublished
        )
        return posts
    except ForbiddenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
```

### Step 7: Register the Router

```python
# src/main.py (add to existing routers)
from .api.routers import auth, test, users, items, blog_posts

app.include_router(blog_posts.router, prefix="/api/v1")
```

## Key Principles Demonstrated

1. **Repository Pattern**: Clean data access abstraction
2. **Service Layer**: Business logic with IDOR protection
3. **Dependency Injection**: Clean separation of concerns
4. **Validation**: Pydantic schemas for request/response
5. **Error Handling**: Custom exceptions with proper HTTP status codes
6. **Security**: Ownership verification and access control
7. **Logging**: Comprehensive audit trail
8. **Pagination**: Standardized pagination patterns

This example shows how to implement a complete feature following the 3-layer architecture while maintaining security, performance, and maintainability.
