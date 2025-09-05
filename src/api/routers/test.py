"""
Test router for system connectivity and health checks.

This router provides endpoints to test database connectivity,
authentication services, and overall system health.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ...core.auth import get_current_active_user, test_keycloak_connection, TokenData
from ...data.database import get_db
from ...core.logging import get_logger
from ...data.repositories.user_repository import UserRepository
from ...data.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/test", tags=["testing"])


class DatabaseStatus(BaseModel):
    """Database connection status."""
    connected: bool
    database_name: str
    version: str
    connection_pool_size: int
    active_connections: int


class SystemHealthResponse(BaseModel):
    """System health check response."""
    status: str
    timestamp: datetime
    services: Dict[str, Any]
    database: DatabaseStatus


class UserCreationRequest(BaseModel):
    """Request model for creating a test user."""
    username: str
    email: str
    first_name: str = ""
    last_name: str = ""


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime


@router.get("/health", response_model=SystemHealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> SystemHealthResponse:
    """
    Comprehensive system health check.

    Args:
        db: Database session

    Returns:
        System health status including all services
    """
    timestamp = datetime.now(timezone.utc)
    services = {}

    # Test database connection
    try:
        # Test basic database connectivity
        result = await db.execute(text("SELECT version(), current_database()"))
        db_info = result.fetchone()

        # Get connection pool info
        pool_info = await db.execute(text("""
            SELECT 
                COUNT(*) as active_connections,
                current_setting('max_connections')::int as max_connections
            FROM pg_stat_activity 
            WHERE state = 'active'
        """))
        pool_data = pool_info.fetchone()

        database_status = DatabaseStatus(
            connected=True,
            database_name=db_info[1] if db_info else "unknown",
            version=db_info[0] if db_info else "unknown",
            connection_pool_size=int(pool_data[1]) if pool_data else 0,
            active_connections=int(pool_data[0]) if pool_data else 0
        )

        services["database"] = {
            "status": "healthy",
            "response_time_ms": "< 100",
            "details": database_status.dict()
        }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_status = DatabaseStatus(
            connected=False,
            database_name="unknown",
            version="unknown",
            connection_pool_size=0,
            active_connections=0
        )
        services["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "details": database_status.dict()
        }

    # Test Keycloak connection
    keycloak_status = await test_keycloak_connection()
    services["keycloak"] = keycloak_status

    # Determine overall health
    overall_status = "healthy" if all(
        service.get("status") in ["healthy", "connected"]
        for service in services.values()
    ) else "unhealthy"

    logger.info(f"Health check completed: {overall_status}")

    return SystemHealthResponse(
        status=overall_status,
        timestamp=timestamp,
        services=services,
        database=database_status
    )


@router.get("/database")
async def test_database_connection(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Test database connectivity and basic operations.

    Args:
        db: Database session

    Returns:
        Database connection test results
    """
    try:
        # Test basic connectivity
        result = await db.execute(text("SELECT 1 as test"))
        test_value = result.scalar()

        # Test current time
        time_result = await db.execute(text("SELECT NOW() as current_time"))
        current_time = time_result.scalar()

        # Test database info
        info_result = await db.execute(text("""
            SELECT 
                version() as pg_version,
                current_database() as database_name,
                current_user as username,
                inet_server_addr() as server_ip,
                inet_server_port() as server_port
        """))
        db_info = info_result.fetchone()

        # Test table existence
        table_result = await db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in table_result.fetchall()]

        logger.info("Database connection test successful")

        return {
            "status": "connected",
            "test_query_result": test_value,
            "server_time": current_time.isoformat() if current_time else None,
            "database_info": {
                "version": db_info[0] if db_info else None,
                "database_name": db_info[1] if db_info else None,
                "username": db_info[2] if db_info else None,
                "server_ip": str(db_info[3]) if db_info and db_info[3] else None,
                "server_port": db_info[4] if db_info else None,
            },
            "tables": tables,
            "connection_successful": True
        }

    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )


@router.post("/create-user", response_model=UserResponse)
async def create_test_user(
    user_data: UserCreationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_active_user)
) -> UserResponse:
    """
    Create a test user to verify database operations.

    Args:
        user_data: User creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created user information
    """
    try:
        user_repo = UserRepository(db)

        # Check if user already exists
        existing_user = await user_repo.get_by_username(user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this username already exists"
            )

        existing_email = await user_repo.get_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create new user
        new_user = await user_repo.create({
            "username": user_data.username,
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "is_active": True
        })

        logger.info(
            f"Test user created: {new_user.username} by {current_user.username}")

        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create test user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get("/users", response_model=List[UserResponse])
async def list_test_users(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_active_user)
) -> List[UserResponse]:
    """
    List all users in the database.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of all users
    """
    try:
        user_repo = UserRepository(db)
        users = await user_repo.get_all()

        logger.info(
            f"Retrieved {len(users)} users for {current_user.username}")

        return [
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            for user in users
        ]

    except Exception as e:
        logger.error(f"Failed to retrieve users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve users: {str(e)}"
        )


@router.delete("/users/{user_id}")
async def delete_test_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Delete a test user by ID.

    Args:
        user_id: User ID to delete
        db: Database session
        current_user: Current authenticated user

    Returns:
        Deletion confirmation
    """
    try:
        user_repo = UserRepository(db)

        # Check if user exists
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Delete user
        await user_repo.delete(user_id)

        logger.info(
            f"Test user {user.username} deleted by {current_user.username}")

        return {"message": f"User {user.username} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.get("/auth-test")
async def test_authentication_flow(
    current_user: TokenData = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Test authentication flow and token validation.

    Args:
        current_user: Current authenticated user

    Returns:
        Authentication test results
    """
    return {
        "message": "Authentication test successful",
        "authenticated_user": {
            "user_id": current_user.user_id,
            "username": current_user.username,
            "email": current_user.email,
            "roles": current_user.roles,
            "token_expiry": current_user.exp.isoformat() if current_user.exp else None
        },
        "test_timestamp": datetime.now(timezone.utc).isoformat(),
        "auth_method": "OAuth2 JWT Bearer",
        "auth_provider": "Keycloak"
    }
