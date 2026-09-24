"""OpenNotebook — Ollama LLM provider (default, local-first)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.llm.base import BaseLLMProvider

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class OllamaProvider(BaseLLMProvider):
    """Provider backed by a local Ollama server."""

    name = "ollama"

    async def stream_generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        from app.infrastructure.ollama.client import stream_generate

        async for token in stream_generate(prompt, model=model, temperature=temperature):
            yield token

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        from app.infrastructure.ollama.client import generate

        return await generate(prompt, model=model, temperature=temperature)
