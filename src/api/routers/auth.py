"""
Authentication router for OAuth2 integration with Keycloak.

This router provides endpoints for user authentication, login, logout,
and user management operations.
"""

from typing import Dict, Any
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ...core.auth import (
    get_current_active_user,
    get_current_user,
    exchange_code_for_token,
    get_keycloak_user_info,
    test_keycloak_connection,
    TokenData,
    KeycloakUser
)
from ...core.config import settings
from ...core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginUrlResponse(BaseModel):
    """Response model for login URL."""
    login_url: str
    state: str


class TokenResponse(BaseModel):
    """Response model for token information."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    user: KeycloakUser


@router.get("/login", response_model=LoginUrlResponse)
async def get_login_url(
    redirect_uri: str = Query(...,
                              description="Redirect URI after authentication")
) -> LoginUrlResponse:
    """
    Get Keycloak login URL for OAuth2 authentication.

    Args:
        redirect_uri: URL to redirect to after authentication

    Returns:
        Login URL and state parameter
    """
    import uuid

    state = str(uuid.uuid4())

    # Build Keycloak authorization URL
    auth_params = {
        "client_id": settings.keycloak_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }

    auth_url = f"{settings.keycloak_base_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/auth"
    login_url = f"{auth_url}?{urlencode(auth_params)}"

    logger.info(f"Generated login URL for redirect_uri: {redirect_uri}")

    return LoginUrlResponse(login_url=login_url, state=state)


@router.post("/callback", response_model=TokenResponse)
async def auth_callback(
    code: str = Query(..., description="Authorization code from Keycloak"),
    state: str = Query(..., description="State parameter for security"),
    redirect_uri: str = Query(..., description="Original redirect URI")
) -> TokenResponse:
    """
    Handle OAuth2 callback and exchange code for tokens.

    Args:
        code: Authorization code from Keycloak
        state: State parameter for security verification
        redirect_uri: Original redirect URI used in authorization request

    Returns:
        Access token and user information
    """
    try:
        # Exchange code for tokens
        token_data = await exchange_code_for_token(code, redirect_uri)

        # Get user information
        user_info = await get_keycloak_user_info(token_data["access_token"])

        logger.info(f"User authenticated successfully: {user_info.username}")

        return TokenResponse(
            access_token=token_data["access_token"],
            token_type="bearer",
            expires_in=token_data["expires_in"],
            refresh_token=token_data.get("refresh_token", ""),
            user=user_info
        )

    except Exception as e:
        logger.error(f"Authentication callback failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed"
        )


@router.get("/me", response_model=TokenData)
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_active_user)
) -> TokenData:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user information
    """
    logger.info(f"User info requested for: {current_user.username}")
    return current_user


@router.post("/logout")
async def logout(
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Logout current user (invalidate token on client side).

    Args:
        current_user: Current authenticated user

    Returns:
        Logout confirmation
    """
    logger.info(f"User logged out: {current_user.username}")

    # In a real implementation, you might want to:
    # 1. Add token to a blacklist
    # 2. Call Keycloak logout endpoint
    # 3. Clear session data

    return {"message": "Successfully logged out"}


@router.get("/test-connection")
async def test_auth_connection() -> Dict[str, Any]:
    """
    Test connection to Keycloak authentication server.

    Returns:
        Connection status and server information
    """
    result = await test_keycloak_connection()
    logger.info(f"Keycloak connection test: {result['status']}")
    return result


@router.get("/protected")
async def protected_endpoint(
    current_user: TokenData = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Protected endpoint that requires authentication.

    Args:
        current_user: Current authenticated user

    Returns:
        Protected resource data
    """
    return {
        "message": "This is a protected endpoint",
        "user": current_user.username,
        "user_id": current_user.user_id,
        "roles": current_user.roles,
        "access_granted_at": "2025-09-05T20:54:00Z"
    }
