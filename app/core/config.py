"""
Application configuration settings
"""
import os


class Settings:
    """Application settings"""

    # JWT Settings
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "your-secret-key-change-this-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database Settings
    DATABASE_URL: str = "sqlite:///./wireguard.db"

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "WireGuard Client Manager API"
    PROJECT_VERSION: str = "1.0.0"
    PROJECT_DESCRIPTION: str = "REST API for managing WireGuard VPN clients"

    # CORS Settings
    BACKEND_CORS_ORIGINS: list = ["*"]  # Configure for production


settings = Settings()
