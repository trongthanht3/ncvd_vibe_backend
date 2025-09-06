"""
Authentication utilities for JWT token validation, OAuth2 integration, and direct authentication.

This module provides JWT token validation, user authentication,
integration with Keycloak OAuth2 server, and direct username/password authentication.
"""

import base64
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from .config import settings
from .logging import get_logger
from .security import verify_access_token, SecurityError

logger = get_logger(__name__)

# Security scheme for Bearer token
security = HTTPBearer()


class TokenData(BaseModel):
    """Token data extracted from JWT."""
    username: Optional[str] = None
    email: Optional[str] = None
    user_id: Optional[str] = None
    roles: list[str] = []
    exp: Optional[datetime] = None


class KeycloakUser(BaseModel):
    """Keycloak user information."""
    id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: list[str] = []
    enabled: bool = True


class DirectLoginRequest(BaseModel):
    """Request model for direct authentication login."""
    email: EmailStr
    password: str


class DirectAuthTokenData(BaseModel):
    """Token data for direct authentication users."""
    user_id: str
    username: str
    email: str
    is_keycloak_user: bool = False
    exp: Optional[datetime] = None


async def get_keycloak_public_key() -> str:
    """
    Fetch Keycloak public key for JWT validation.

    Returns:
        Public key string for JWT verification

    Raises:
        HTTPException: If unable to fetch public key
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}"
            )
            response.raise_for_status()
            realm_info = response.json()
            return realm_info["public_key"]
    except Exception as e:
        logger.error(f"Failed to fetch Keycloak public key: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable"
        )


async def verify_token(token: str) -> TokenData:
    """
    Verify JWT token and extract user information.

    Args:
        token: JWT token string

    Returns:
        TokenData with user information

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Validate token format and encoding
        if not token or not isinstance(token, str):
            raise ValueError("Invalid token format")

        # Check if token can be encoded as UTF-8 (basic validation)
        try:
            token.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError("Token contains invalid characters")

        # Basic JWT format validation (should have 3 parts separated by dots)
        token_parts = token.split('.')
        if len(token_parts) != 3:
            raise ValueError("Invalid JWT format: must have 3 parts")

        # Validate each part can be base64 decoded (with padding if needed)
        for i, part in enumerate(token_parts):
            try:
                # Add padding if needed for base64 decoding
                missing_padding = len(part) % 4
                if missing_padding:
                    part += '=' * (4 - missing_padding)
                base64.urlsafe_b64decode(part)
            except Exception as e:
                raise ValueError(
                    f"Invalid base64 encoding in JWT part {i + 1}: {e}")

        # Get public key from Keycloak
        public_key = await get_keycloak_public_key()

        # Verify and decode token
        payload = jwt.decode(
            token,
            f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----",
            algorithms=["RS256"],
            audience=settings.keycloak_client_id
        )

        # Extract user information
        username = payload.get("preferred_username")
        email = payload.get("email")
        user_id = payload.get("sub")

        # Extract roles from realm_access or resource_access
        roles = []
        if "realm_access" in payload:
            roles.extend(payload["realm_access"].get("roles", []))
        if "resource_access" in payload and settings.keycloak_client_id in payload["resource_access"]:
            roles.extend(payload["resource_access"]
                         [settings.keycloak_client_id].get("roles", []))

        # Get expiration time
        exp_timestamp = payload.get("exp")
        exp = datetime.fromtimestamp(
            exp_timestamp, tz=timezone.utc) if exp_timestamp else None

        return TokenData(
            username=username,
            email=email,
            user_id=user_id,
            roles=roles,
            exp=exp
        )

    except ValueError as e:
        token_info = sanitize_token_for_logging(token)
        logger.warning(f"Token format validation failed for {token_info}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        token_info = sanitize_token_for_logging(token)
        logger.warning(f"JWT validation failed for {token_info}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except UnicodeDecodeError as e:
        token_info = sanitize_token_for_logging(token)
        logger.warning(f"Token encoding error for {token_info}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token encoding",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        token_info = sanitize_token_for_logging(token)
        logger.error(f"Token verification error for {token_info}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    Get current authenticated user from JWT token (Keycloak or direct auth).

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        TokenData with current user information

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials or not credentials.credentials:
        logger.warning("Missing or empty authorization credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    token_info = sanitize_token_for_logging(token)
    logger.debug(f"Processing token: {token_info}")

    # Try direct auth token verification first
    try:
        payload = verify_access_token(token)

        # This is a direct auth token
        if payload.get("type") == "access" and payload.get("user_id"):
            return TokenData(
                username=payload.get("username"),
                email=payload.get("email"),
                user_id=payload.get("user_id"),
                roles=payload.get("roles", []),
                exp=datetime.fromtimestamp(
                    payload["exp"], tz=timezone.utc) if payload.get("exp") else None
            )
    except SecurityError:
        # Not a direct auth token, try Keycloak token
        pass

    # Fall back to Keycloak token verification
    return await verify_token(token)


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Get current active user (additional validation can be added here).

    Args:
        current_user: Current user token data

    Returns:
        Validated current user

    Raises:
        HTTPException: If user is inactive or validation fails
    """
    # Check if token is expired
    if current_user.exp and current_user.exp < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user


def require_role(required_role: str):
    """
    Dependency factory for role-based access control.

    Args:
        required_role: Required role for access

    Returns:
        Dependency function that checks for the required role
    """
    def role_checker(current_user: TokenData = Depends(get_current_active_user)) -> TokenData:
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role} role"
            )
        return current_user

    return role_checker


async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access token with Keycloak.

    Args:
        code: Authorization code from Keycloak
        redirect_uri: Redirect URI used in authorization request

    Returns:
        Token response from Keycloak

    Raises:
        HTTPException: If token exchange fails
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.keycloak_client_id,
                    "client_secret": settings.keycloak_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Failed to exchange code for token: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorization code"
        )


async def get_keycloak_user_info(access_token: str) -> KeycloakUser:
    """
    Get user information from Keycloak using access token.

    Args:
        access_token: Keycloak access token

    Returns:
        KeycloakUser with user information

    Raises:
        HTTPException: If unable to fetch user info
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            user_data = response.json()

            return KeycloakUser(
                id=user_data["sub"],
                username=user_data.get("preferred_username", ""),
                email=user_data.get("email", ""),
                first_name=user_data.get("given_name"),
                last_name=user_data.get("family_name"),
                roles=[],  # Roles are typically in the JWT token, not userinfo
                enabled=True
            )
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to fetch user information"
        )


async def test_keycloak_connection() -> Dict[str, Any]:
    """
    Test connection to Keycloak server.

    Returns:
        Connection status and server information
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test realm endpoint
            response = await client.get(
                f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}"
            )
            response.raise_for_status()
            realm_info = response.json()

            return {
                "status": "connected",
                "realm": realm_info.get("realm"),
                "public_key_available": bool(realm_info.get("public_key")),
                "server_url": settings.keycloak_base_url
            }
    except Exception as e:
        logger.error(f"Keycloak connection test failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "server_url": settings.keycloak_base_url
        }


def sanitize_token_for_logging(token: str, max_length: int = 20) -> str:
    """
    Sanitize token string for safe logging.

    Args:
        token: The token to sanitize
        max_length: Maximum length to show

    Returns:
        Sanitized token string safe for logging
    """
    if not token:
        return "<empty>"

    if len(token) <= max_length:
        return f"<token:{len(token)}chars>"

    return f"<token:{len(token)}chars:{token[:10]}...{token[-4:]}>"


# Direct authentication functions

async def authenticate_user_direct(email: str, password: str) -> Optional[DirectAuthTokenData]:
    """
    Authenticate user with email and password (direct authentication).

    Args:
        email: User email address
        password: User password

    Returns:
        DirectAuthTokenData if authentication successful, None otherwise
    """
    from ..data.database import get_db_session
    from ..data.models.user import User
    from sqlalchemy import select

    session = None
    try:
        session = await get_db_session()

        # Find user by email
        stmt = select(User).where(User.email == email, User.is_active == True)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"Login attempt for non-existent user: {email}")
            return None

        # Check if account is locked
        if user.is_account_locked:
            logger.warning(f"Login attempt for locked account: {email}")
            return None

        # Verify password
        if not user.verify_password(password):
            # Record failed login attempt
            user.record_failed_login()
            await session.commit()
            logger.warning(f"Failed login attempt for user: {email}")
            return None

        # Authentication successful
        user.record_successful_login()
        await session.commit()

        logger.info(f"Successful direct authentication for user: {email}")

        return DirectAuthTokenData(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            is_keycloak_user=False
        )

    except Exception as e:
        logger.error(f"Error during direct authentication for {email}: {e}")
        if session:
            await session.rollback()
        return None
    finally:
        if session:
            await session.close()


async def create_user_direct(
    email: str,
    password: str,
    username: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> Optional[DirectAuthTokenData]:
    """
    Create a new user with direct authentication.

    Args:
        email: User email address
        password: User password
        username: Username
        first_name: Optional first name
        last_name: Optional last name

    Returns:
        DirectAuthTokenData if user creation successful, None otherwise
    """
    from ..data.database import get_db_session
    from ..data.models.user import User
    from sqlalchemy import select

    session = None
    try:
        session = await get_db_session()

        # Check if user already exists
        stmt = select(User).where(
            (User.email == email) | (User.username == username)
        )
        existing_user = await session.execute(stmt)
        if existing_user.scalar_one_or_none():
            logger.warning(
                f"User creation failed - user already exists: {email}")
            return None

        # Create new user
        user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_verified=False  # Email verification can be implemented later
        )

        # Set password
        user.set_password(password)

        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info(f"New user created with direct auth: {email}")

        return DirectAuthTokenData(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            is_keycloak_user=False
        )

    except Exception as e:
        logger.error(f"Error creating user {email}: {e}")
        if session:
            await session.rollback()
        return None
    finally:
        if session:
            await session.close()
