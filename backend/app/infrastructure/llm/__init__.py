"""OpenNotebook — LLM provider factory and public exports."""

from __future__ import annotations

from app.core.config import get_settings
from app.infrastructure.llm.base import BaseLLMProvider
from app.infrastructure.llm.ollama_provider import OllamaProvider

__all__ = ["BaseLLMProvider", "OllamaProvider", "get_llm_provider"]


def get_llm_provider(provider: str | None = None) -> BaseLLMProvider:
    """Return the configured LLM provider.

    Args:
        provider: Override name (``ollama`` | ``openai`` | ``anthropic`` | ``gemini``).
            Defaults to the ``llm_provider`` setting with auto-detection for cloud API keys.
    """
    settings = get_settings()
    name = (provider or settings.llm_provider or "ollama").lower()

    # Smart auto-detection: if default 'ollama' is specified but cloud API keys are present,
    # auto-route to cloud provider (Gemini -> OpenAI -> Anthropic)
    if name == "ollama":
        if settings.gemini_api_key:
            name = "gemini"
        elif settings.openai_api_key:
            name = "openai"
        elif settings.anthropic_api_key:
            name = "anthropic"

    if name == "ollama":
        return OllamaProvider()
    if name in ("openai", "openai_compatible"):
        from app.infrastructure.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == "anthropic":
        from app.infrastructure.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name in ("gemini", "google"):
        from app.infrastructure.llm.gemini_provider import GeminiProvider

        return GeminiProvider()

    raise ValueError(f"Unknown LLM provider: {name!r}")
