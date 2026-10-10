"""Configuration module for Czech Elections 2026 MCP Server.

All settings are parameterized and configurable via environment variables
or a .env file. No magic hardcoded values are embedded in business logic.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8088
    API_KEY: str | None = None
    CORS_ORIGINS: List[str] = ["*"]

    # Official CSU (Czech Statistical Office) election endpoints
    CSU_BASE_URL: str = "https://volby.gov.cz"
    SENAT_ELECTION_CODE: str = "20261009"
    KV_ELECTION_CODE: str = "20261009"
    KV_VERSION: str = "kv2026"

    # HTTP client & caching configuration
    CACHE_TTL_SECONDS: int = 30
    HTTP_TIMEOUT_SECONDS: float = 15.0
    HTTP_MAX_RETRIES: int = 3
    USER_AGENT: str = "CzechElectionsMCP/1.0 (+https://volby.gov.cz; AI Assistant Integration)"

    # Storage paths
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton instance
settings = Settings()
