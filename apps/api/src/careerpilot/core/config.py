from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    """Validated at start-up: the app refuses to run with missing or malformed settings."""

    model_config = SettingsConfigDict(
        env_prefix="CAREERPILOT_", env_file=REPO_ROOT / ".env", extra="ignore"
    )

    database_url: str
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_origins: list[str] = ["http://localhost:3100", "http://127.0.0.1:3100"]
    cookie_secure: bool = False
    session_ttl_hours: int = Field(default=24 * 7, ge=1)
    login_max_failures: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=900, ge=1)
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must start with postgresql+asyncpg://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
