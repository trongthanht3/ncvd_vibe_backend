"""
Security utilities and configurations.

This module provides security-related utilities including input validation,
SSRF protection, password hashing, JWT token generation, and other security measures.
"""

import ipaddress
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union, Dict, Any

import bcrypt
from jose import jwt
from urllib.parse import urlparse

from .config import settings


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class SSRFError(SecurityError):
    """Exception raised when SSRF attack is detected."""
    pass


class InputValidationError(SecurityError):
    """Exception raised when input validation fails."""
    pass


def validate_url_for_ssrf(url: str, allowed_schemes: Optional[List[str]] = None) -> str:
    """
    Validate URL to prevent Server-Side Request Forgery (SSRF) attacks.

    Args:
        url: URL to validate
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])

    Returns:
        Validated URL

    Raises:
        SSRFError: If URL is potentially dangerous
        InputValidationError: If URL format is invalid
    """
    if not url:
        raise InputValidationError("URL cannot be empty")

    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise InputValidationError(f"Invalid URL format: {e}")

    # Check scheme
    if parsed.scheme not in allowed_schemes:
        raise SSRFError(
            f"Scheme '{parsed.scheme}' not allowed. Allowed schemes: {allowed_schemes}")

    # Check for missing host
    if not parsed.hostname:
        raise InputValidationError("URL must have a hostname")

    # Check for private/internal IP ranges
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        if _is_private_ip(ip):
            raise SSRFError(
                f"Private IP address not allowed: {parsed.hostname}")
    except ValueError:
        # Not an IP address, check for localhost/internal hostnames
        if _is_internal_hostname(parsed.hostname):
            raise SSRFError(
                f"Internal hostname not allowed: {parsed.hostname}")

    # Check port restrictions
    if parsed.port:
        if _is_restricted_port(parsed.port):
            raise SSRFError(f"Port {parsed.port} not allowed")

    return url


def _is_private_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """
    Check if IP address is in private/internal ranges.

    Args:
        ip: IP address to check

    Returns:
        True if IP is private/internal
    """
    if isinstance(ip, ipaddress.IPv4Address):
        # Private IPv4 ranges
        private_ranges = [
            ipaddress.IPv4Network('10.0.0.0/8'),       # Private
            ipaddress.IPv4Network('172.16.0.0/12'),    # Private
            ipaddress.IPv4Network('192.168.0.0/16'),   # Private
            ipaddress.IPv4Network('127.0.0.0/8'),      # Loopback
            ipaddress.IPv4Network('169.254.0.0/16'),   # Link-local
            ipaddress.IPv4Network('224.0.0.0/4'),      # Multicast
            ipaddress.IPv4Network('240.0.0.0/4'),      # Reserved
        ]
        return any(ip in network for network in private_ranges)

    elif isinstance(ip, ipaddress.IPv6Address):
        # Private IPv6 ranges
        private_ranges = [
            ipaddress.IPv6Network('::1/128'),          # Loopback
            ipaddress.IPv6Network('fc00::/7'),         # Unique local
            ipaddress.IPv6Network('fe80::/10'),        # Link-local
            ipaddress.IPv6Network('ff00::/8'),         # Multicast
        ]
        return any(ip in network for network in private_ranges)

    return False


def _is_internal_hostname(hostname: str) -> bool:
    """
    Check if hostname is internal/localhost.

    Args:
        hostname: Hostname to check

    Returns:
        True if hostname is internal
    """
    internal_hostnames = {
        'localhost',
        'localhost.localdomain',
        '127.0.0.1',
        '::1',
        'metadata.google.internal',  # Google Cloud metadata service
        '169.254.169.254',           # AWS metadata service
    }

    hostname_lower = hostname.lower()

    # Exact matches
    if hostname_lower in internal_hostnames:
        return True

    # Pattern matches
    internal_patterns = [
        r'^localhost$',
        r'^.*\.localhost$',
        r'^.*\.local$',
        r'^.*\.internal$',
        r'^metadata\..*',
    ]

    return any(re.match(pattern, hostname_lower) for pattern in internal_patterns)


def _is_restricted_port(port: int) -> bool:
    """
    Check if port is restricted.

    Args:
        port: Port number to check

    Returns:
        True if port is restricted
    """
    # Common restricted ports (services that shouldn't be accessible externally)
    restricted_ports = {
        22,    # SSH
        23,    # Telnet
        25,    # SMTP
        53,    # DNS
        110,   # POP3
        143,   # IMAP
        993,   # IMAPS
        995,   # POP3S
        1433,  # SQL Server
        1521,  # Oracle
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        9200,  # Elasticsearch
        27017,  # MongoDB
    }

    return port in restricted_ports


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks.

    Args:
        filename: Original filename
        max_length: Maximum allowed filename length

    Returns:
        Sanitized filename

    Raises:
        InputValidationError: If filename is invalid
    """
    if not filename:
        raise InputValidationError("Filename cannot be empty")

    # Remove path separators and dangerous characters
    dangerous_chars = ['/', '\\', '..', '<',
                       '>', ':', '"', '|', '?', '*', '\0']
    sanitized = filename

    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '_')

    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')

    # Check length
    if len(sanitized) > max_length:
        name, ext = sanitized.rsplit(
            '.', 1) if '.' in sanitized else (sanitized, '')
        max_name_length = max_length - len(ext) - 1 if ext else max_length
        sanitized = name[:max_name_length] + ('.' + ext if ext else '')

    # Ensure filename is not empty after sanitization
    if not sanitized:
        raise InputValidationError("Filename invalid after sanitization")

    return sanitized


def mask_sensitive_value(value: str, mask_char: str = '*', visible_chars: int = 4) -> str:
    """
    Mask sensitive values for logging.

    Args:
        value: Sensitive value to mask
        mask_char: Character to use for masking
        visible_chars: Number of characters to show at the end

    Returns:
        Masked value
    """
    if not value or len(value) <= visible_chars:
        return mask_char * 8

    return mask_char * (len(value) - visible_chars) + value[-visible_chars:]


# Password hashing utilities

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password as string
    """
    # Convert string to bytes for bcrypt
    password_bytes = password.encode('utf-8')

    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    try:
        # Convert strings to bytes for bcrypt
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')

        # Verify password
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        # Return False for any error (invalid hash format, etc.)
        return False


# JWT token utilities

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        JWT token string
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + \
            timedelta(hours=1)  # Default 1 hour

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    # Create JWT token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm="HS256"
    )

    return encoded_jwt


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT access token.

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload

    Raises:
        SecurityError: If token is invalid or expired
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"]
        )

        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            raise SecurityError("Token missing expiration")

        exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
        if datetime.now(timezone.utc) > exp_datetime:
            raise SecurityError("Token expired")

        return payload

    except jwt.JWTError as e:
        raise SecurityError(f"Invalid token: {e}")
    except Exception as e:
        raise SecurityError(f"Token verification failed: {e}")


def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User ID to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        JWT refresh token string
    """
    data = {"sub": user_id, "type": "refresh"}

    # Set expiration time (longer for refresh tokens)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + \
            timedelta(days=30)  # Default 30 days

    data.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    # Create JWT token
    encoded_jwt = jwt.encode(
        data,
        settings.secret_key,
        algorithm="HS256"
    )

    return encoded_jwt
