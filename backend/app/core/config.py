"""OpenNotebook — Application configuration via Pydantic Settings.

All configuration is loaded from environment variables.
See .env.example for the full list of supported variables.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────
    app_name: str = "opennotebook"
    app_env: str = "development"
    debug: bool = True

    # ── Database ─────────────────────────────────
    database_url: str = "postgresql+asyncpg://opennotebook:opennotebook@localhost:5432/opennotebook"

    # ── Auth (JWT) ───────────────────────────────
    jwt_secret_key: str = "change-me-to-a-random-64-char-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── Password Hashing ─────────────────────────
    bcrypt_cost_factor: int = 12

    # ── CORS ─────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Accept comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Logging ──────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"

    # ── Redis ────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── File Upload ──────────────────────────────
    max_upload_size_mb: int = 50
    max_files_per_request: int = 10

    # ── MinIO (Object Storage) ───────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "opennotebook"
    minio_secure: bool = False

    # ── Qdrant (Vector Store) ────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "opennotebook_chunks"

    # ── Celery (Task Queue) ──────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Embedding Model ──────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_batch_size: int = 64
    embedding_dimension: int = 384


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
