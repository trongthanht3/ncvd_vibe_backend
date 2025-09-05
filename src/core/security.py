"""
Security utilities and configurations.

This module provides security-related utilities including input validation,
SSRF protection, and other security measures.
"""

import ipaddress
import re
from typing import List, Optional, Union
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
