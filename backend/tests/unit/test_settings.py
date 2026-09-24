"""OpenNotebook — Unit tests for settings loading edge cases."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_accepts_comma_separated_string(monkeypatch):
    """CORS_ORIGINS as a comma-separated string (as in .env) must not crash parsing."""
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    settings = Settings()
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_cors_origins_defaults_to_localhost():
    settings = Settings()
    assert "http://localhost:5173" in settings.cors_origins


def test_llm_provider_default():
    assert Settings().llm_provider == "ollama"


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="change-me-to-a-random-64-char-string",
            minio_secret_key="strong-secret",
        )


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret_key="short", minio_secret_key="strong-secret")


def test_production_accepts_strong_secrets():
    settings = Settings(
        app_env="production",
        jwt_secret_key="x" * 64,
        minio_secret_key="strong-secret",
    )
    assert settings.app_env == "production"


def test_development_allows_defaults():
    assert Settings(app_env="development").jwt_secret_key
