"""
Application configuration using Pydantic Settings.

This module provides centralized configuration management for the FastAPI application,
loading settings from environment variables with validation and type safety.
"""

from typing import List, Optional
from pydantic import Field, validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    For example, APP_ENV can be set to override the app_env setting.
    """

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields
        case_sensitive=False
    )

    # Application settings
    app_env: str = Field(default="development",
                         description="Application environment")
    app_debug: bool = Field(default=False, description="Enable debug mode")
    app_host: str = Field(default="0.0.0.0", description="Application host")
    app_port: int = Field(default=8000, description="Application port")
    secret_key: str = Field(..., description="Secret key for encryption")

    # Database settings
    database_url: str = Field(..., description="PostgreSQL database URL")

    # Keycloak settings
    keycloak_base_url: str = Field(..., description="Keycloak base URL")
    keycloak_realm: str = Field(..., description="Keycloak realm name")
    keycloak_audience: str = Field(..., description="Expected JWT audience")
    keycloak_client_id: str = Field(..., description="Keycloak client ID")
    keycloak_client_secret: Optional[str] = Field(
        default=None, description="Keycloak client secret (for introspection)"
    )
    jwks_cache_ttl: int = Field(
        default=3600, description="JWKS cache TTL in seconds")

    # CORS settings
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )

    # Milvus settings
    milvus_host: str = Field(default="localhost", description="Milvus host")
    milvus_port: int = Field(default=19530, description="Milvus port")
    milvus_username: Optional[str] = Field(
        default=None, description="Milvus username")
    milvus_password: Optional[str] = Field(
        default=None, description="Milvus password")

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="json", description="Logging format (json/text)")

    # Development settings
    reload: bool = Field(default=False, description="Enable auto-reload")

    @property
    def cors_origins_list(self) -> List[str]:
        """
        Get CORS origins as a list.

        Returns:
            List of CORS origin strings
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @validator("log_level")
    def validate_log_level(cls, v):
        """
        Validate log level is one of the allowed values.

        Args:
            v: Log level string

        Returns:
            Validated log level

        Raises:
            ValueError: If log level is invalid
        """
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f"Log level must be one of: {allowed_levels}")
        return v.upper()

    @validator("log_format")
    def validate_log_format(cls, v):
        """
        Validate log format is one of the allowed values.

        Args:
            v: Log format string

        Returns:
            Validated log format

        Raises:
            ValueError: If log format is invalid
        """
        allowed_formats = ["json", "text"]
        if v.lower() not in allowed_formats:
            raise ValueError(f"Log format must be one of: {allowed_formats}")
        return v.lower()


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings instance
    """
    return settings
