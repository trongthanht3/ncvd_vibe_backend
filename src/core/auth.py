"""
Authentication utilities for JWT token validation and OAuth2 integration.

This module provides JWT token validation, user authentication,
and integration with Keycloak OAuth2 server.
"""

import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings
from .logging import get_logger

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

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        TokenData with current user information

    Raises:
        HTTPException: If authentication fails
    """
    return await verify_token(credentials.credentials)


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
