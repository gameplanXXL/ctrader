"""Application configuration via pydantic-settings.

Loads from environment variables and .env file. All secrets live here —
never hardcode credentials anywhere else in the codebase.

References:
- NFR-S1: API credentials exclusively in .env / env-vars
- NFR-S2: FastAPI binds to 127.0.0.1 only
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    host: str = Field(default="127.0.0.1", description="Bind address (NFR-S2: 127.0.0.1 only)")
    port: int = Field(default=8000, description="Bind port")

    # ------------------------------------------------------------------
    # Database (PostgreSQL via asyncpg)
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql://ctrader:ctrader@127.0.0.1:5432/ctrader",
        description="PostgreSQL DSN, passed directly to asyncpg.create_pool()",
    )
    db_pool_min_size: int = Field(default=2, description="asyncpg pool min_size")
    db_pool_max_size: int = Field(default=10, description="asyncpg pool max_size")

    # ------------------------------------------------------------------
    # Logging (structlog JSON)
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", description="structlog/stdlib log level")
    log_file: str = Field(
        default="data/logs/ctrader.log",
        description="Log file path — rotated at 100MB, 5 backups (NFR-M4)",
    )
    log_file_max_bytes: int = Field(default=100 * 1024 * 1024, description="100 MB per file")
    log_file_backup_count: int = Field(default=5, description="5 rotations (NFR-M4)")

    # ------------------------------------------------------------------
    # Environment
    # ------------------------------------------------------------------
    environment: str = Field(
        default="development",
        description="development | production — gates dev-only features",
    )

    # ------------------------------------------------------------------
    # MCP fundamental — Story 1.6
    # ------------------------------------------------------------------
    mcp_fundamental_url: str | None = Field(
        default=None,
        description=(
            "Base URL of the fundamental MCP server. None = MCP unavailable, "
            "app starts with mcp_available=False (graceful degradation)."
        ),
    )


# Singleton instance. Import this, not Settings() directly.
settings = Settings()
