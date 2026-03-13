"""
Application configuration settings.
"""
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"

    secret_key: SecretStr | None = Field(default=None, alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    database_url: str = "sqlite:///./wireguard.db"

    project_name: str = "WireGuard Client Manager API"
    project_version: str = "1.0.0"
    project_description: str = "REST API for managing WireGuard VPN clients"
    api_prefix: str = "/api"

    backend_cors_origins_raw: str | list[str] | None = Field(
        default=None,
        alias="BACKEND_CORS_ORIGINS",
    )

    wireguard_interface: str = "wg0"
    wireguard_config_path: Path = Path("/etc/wireguard/wg0.conf")
    wireguard_client_config_dir: Path = Path("/opt/wg-ui/data")

    bootstrap_admin_enabled: bool = False
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: SecretStr | None = None

    @field_validator("backend_cors_origins_raw", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]

    @field_validator("access_token_expire_minutes")
    @classmethod
    def validate_access_token_expiry(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_bootstrap_admin(self) -> "Settings":
        if self.bootstrap_admin_enabled and (
            not self.bootstrap_admin_username or not self.bootstrap_admin_password
        ):
            raise ValueError(
                "BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD are required "
                "when BOOTSTRAP_ADMIN_ENABLED=true"
            )
        return self

    @property
    def sqlalchemy_connect_args(self) -> dict[str, bool]:
        if self.database_url.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}

    @property
    def cors_origins(self) -> list[str]:
        return list(self.backend_cors_origins_raw or [])


settings = Settings()
