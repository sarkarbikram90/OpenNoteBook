"""OpenNotebook — Unit tests for settings loading edge cases."""

from __future__ import annotations

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
