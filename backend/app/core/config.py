"""OpenNotebook — Application configuration via Pydantic Settings.

All configuration is loaded from environment variables.
See .env.example for the full list of supported variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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

    @field_validator("database_url", mode="before")
    @classmethod
    def parse_database_url(cls, v: str) -> str:
        """Handle empty string, normalize driver, escape passwords, and adapt IPv6-only hosts."""
        import re
        import urllib.parse

        if not v or not isinstance(v, str) or not v.strip():
            return "postgresql+asyncpg://opennotebook:opennotebook@localhost:5432/opennotebook"

        val = v.strip()
        if val.startswith("postgres://"):
            val = "postgresql+asyncpg://" + val[len("postgres://"):]
        elif val.startswith("postgresql://") and not val.startswith("postgresql+asyncpg://"):
            val = "postgresql+asyncpg://" + val[len("postgresql://"):]

        # Handle unescaped characters in password (e.g. '@' in password) first
        if "://" in val and "@" in val:
            scheme, rest = val.split("://", 1)
            userinfo, hostinfo = rest.rsplit("@", 1)
            if ":" in userinfo:
                user, password = userinfo.split(":", 1)
                encoded_pwd = urllib.parse.quote(urllib.parse.unquote(password), safe="")
                val = f"{scheme}://{user}:{encoded_pwd}@{hostinfo}"

        # Supabase direct host (db.<project_ref>.supabase.co) only has IPv6 (AAAA) DNS records.
        # Google Cloud Run outbound networking operates on IPv4 by default.
        # The verified active IPv4 Transaction Pooler for project ixjaquviwwtfrdenybxc is:
        # aws-1-ap-southeast-1.pooler.supabase.com:6543 with user postgres.ixjaquviwwtfrdenybxc
        if "ixjaquviwwtfrdenybxc" in val:
            scheme, rest = val.split("://", 1)
            userinfo, _ = rest.split("@", 1)
            if ":" in userinfo:
                user, pwd = userinfo.split(":", 1)
                if user == "postgres":
                    user = "postgres.ixjaquviwwtfrdenybxc"
                userinfo = f"{user}:{pwd}"
            val = f"{scheme}://{userinfo}@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

        return val

    # ── Auth (JWT) ───────────────────────────────
    jwt_secret_key: str = "change-me-to-a-random-64-char-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── Password Hashing ─────────────────────────
    bcrypt_cost_factor: int = 12

    # ── CORS ─────────────────────────────────────
    # NoDecode: accept a plain comma-separated string (as in .env) instead of
    # requiring a JSON array; the validator below splits it.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

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

    # ── MinIO / Storage (Object Storage / Data Lake) ────
    storage_provider: str = "minio"  # "minio", "s3", or "local"
    local_storage_path: str = "./data/lake"
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
    connector_poll_seconds: int = 60

    # ── Embedding Model ──────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_batch_size: int = 64
    embedding_dimension: int = 384

    # ── Ollama (LLM Inference) ───────────────────
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b-instruct"
    ollama_temperature: float = 0.1

    # ── LLM Provider (pluggable) ─────────────────
    llm_provider: str = "ollama"  # ollama | openai | anthropic | gemini
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-sonnet-latest"
    anthropic_max_tokens: int = 1024
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_model: str = "gemini-1.5-flash"

    # ── Reranker ─────────────────────────────────
    reranker_model: str = "BAAI/bge-reranker-base"

    # ── Retrieval ────────────────────────────────
    retrieval_top_k: int = 20
    rerank_top_k: int = 10
    rrf_k: int = 60
    max_history_messages: int = 10

    # ── Governance / PII ─────────────────────────
    pii_engine: str = "auto"  # "regex" | "presidio" | "auto"
    pii_redaction_enabled: bool = True

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> Settings:
        """Refuse to start in production with default/placeholder secrets."""
        if self.app_env.lower() in ("production", "prod"):
            weak = {
                "",
                "change-me",
                "change-me-to-a-random-64-char-string",
                "change-me-to-a-random-64-char-string-for-prod-security-keys",
            }
            if self.jwt_secret_key in weak or len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be a strong, unique value in production")
            if self.minio_secret_key in weak:
                raise ValueError("MINIO_SECRET_KEY must be set in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
