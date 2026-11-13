"""
ACS Control - Application settings.

Configuration is loaded from environment variables and, optionally,
from a .env file.

Default:
    <project-root>/.env

Custom location:
    ACS_CONTROL_ENV_FILE=/path/to/private/.env

Never commit a production .env file to the repository.
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = Path(
    os.getenv(
        "ACS_CONTROL_ENV_FILE",
        PROJECT_ROOT / ".env",
    )
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "ACS Control"
    app_env: str = "production"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Regional settings
    timezone: str = "America/Bogota"

    # Security
    app_secret_key: str

    # GenieACS
    genieacs_nbi_url: str
    genieacs_timeout: int = 15

    # PostgreSQL
    database_url: str

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    # Sesiones
    session_hours: int = 12
    # True cuando ACS Control se sirve por HTTPS (la cookie solo viaja cifrada).
    session_cookie_secure: bool = False

    # Logging
    log_level: str = "INFO"


settings = Settings()
