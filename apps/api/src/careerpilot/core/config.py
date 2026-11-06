from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    """Validated at start-up: the app refuses to run with missing or malformed settings."""

    model_config = SettingsConfigDict(
        env_prefix="CAREERPILOT_",
        env_file=REPO_ROOT / ".env",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]
    allowed_origins: list[str] = ["http://localhost:3100", "http://127.0.0.1:3100"]
    cookie_secure: bool = False
    session_ttl_hours: int = Field(default=24 * 7, ge=1)
    login_max_failures: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=900, ge=1)
    log_level: str = "INFO"
    timezone: str = "Asia/Kolkata"
    # Committed guides live in content/guides; private ones (employer-specific) in content/private.
    content_dir: Path = REPO_ROOT / "content"
    # Versioned prompt files (prompts/<name>/vN.md); see core/prompts.py.
    prompts_dir: Path = REPO_ROOT / "prompts"

    # Search over your notes. Embeddings run locally; the model downloads once into model_cache_dir.
    embedder: Literal["fastembed", "hash"] = "fastembed"  # "hash" is a stand-in for tests
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    model_cache_dir: Path = REPO_ROOT / ".cache" / "fastembed"
    # Below this cosine similarity the best passage is treated as "not in your notes". Chosen from
    # `careerpilot eval-rag`: answerable questions scored 0.62 or more, unrelated ones 0.57 or less.
    min_similarity: float = Field(default=0.6, ge=0, le=1)

    # Weight of the full-text ranking next to the vector ranking when fusing them (1 = equal).
    text_weight: float = Field(default=0.2, ge=0, le=1)

    # Optional: with no key, "Ask my notes" returns the matching passages without a written answer.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-sonnet-5-5"
    # Bulk reading (pages, job descriptions) goes to a much cheaper model; judgement (answers with
    # citations, mock interviews, grading) stays on llm_model. Prices per million tokens, from
    # Anthropic's pricing page, 2026-11-06: Haiku 5.5 0.10 in / 0.50 out, Sonnet 5.5 2 in / 10 out.
    llm_model_light: str = "claude-haiku-5-5"
    llm_light_prompts: list[str] = [
        "research-extract",
        "intel-extract",
        "company-pages",
        "jd-reading",
    ]
    llm_daily_token_cap: int = Field(default=200_000, ge=1)

    # Outreach stays personal: at most this many messages can be approved per day.
    outreach_daily_cap: int = Field(default=10, ge=1)

    # Background work (job-board discovery, the daily digest). The worker runs inside the API
    # process while it is up; `python -m careerpilot.cli worker` runs it on its own.
    worker_enabled: bool = True
    worker_poll_seconds: int = Field(default=30, ge=1)
    discovery_hour: int = Field(default=7, ge=0, le=23)  # local time, once a day
    digest_hour: int = Field(default=8, ge=0, le=23)
    task_max_attempts: int = Field(default=3, ge=1, le=10)
    task_stuck_minutes: int = Field(default=15, ge=1)

    # Nightly encrypted backups (core/backup.py). Without a key nothing is backed up.
    backup_key: SecretStr | None = None  # make one with `careerpilot backup-key`
    backup_dir: Path = REPO_ROOT / "backups"
    backup_keep: int = Field(default=14, ge=1)
    backup_hour: int = Field(default=2, ge=0, le=23)  # local time
    pg_dump_path: str = "pg_dump"
    pg_restore_path: str = "pg_restore"
    # Name of the Docker container running Postgres: run the tools inside it (right version).
    pg_container: str | None = None

    # Research agent: which search service to use and how much one run may spend.
    # "searxng" (free, self-hosted; set searxng_url) or "brave" (needs brave_api_key), else "none".
    search_provider: Literal["none", "searxng", "tavily", "brave"] = "none"
    searxng_url: str | None = None
    brave_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    research_max_searches: int = Field(default=10, ge=1, le=30)
    research_max_pages: int = Field(default=12, ge=1, le=40)
    research_max_tokens: int = Field(default=80_000, ge=1000)

    @field_validator(
        "anthropic_api_key", "backup_key", "brave_api_key", "tavily_api_key", mode="before"
    )
    @classmethod
    def _blank_key_means_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must start with postgresql+asyncpg://")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
