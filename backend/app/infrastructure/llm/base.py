"""OpenNotebook — LLM provider interface and shared helpers.

Defines the provider contract used by the RAG serving layer and summarisation
task so the underlying model can be swapped (Ollama, OpenAI, Anthropic, Gemini)
without changing call sites.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Prompt/response types are intentionally simple strings: the RAG orchestrator
# builds a single grounded prompt and streams plain text back.


class BaseLLMProvider:
    """Base class for LLM providers.

    Subclasses implement :meth:`stream_generate` as an async generator of text
    tokens. :meth:`generate` aggregates the stream for non-interactive callers.
    """

    name: str = "base"

    async def stream_generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Yield response tokens for ``prompt``."""
        raise NotImplementedError
        yield ""  # pragma: no cover - marks this as an async generator

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Return the full response for ``prompt`` (aggregated stream)."""
        parts: list[str] = []
        async for token in self.stream_generate(prompt, model=model, temperature=temperature):
            parts.append(token)
        return "".join(parts)


async def iter_sse_data(response: Any) -> AsyncGenerator[str, None]:
    """Yield the payload of each ``data:`` line from an SSE/NDJSON response."""
    async for raw_line in response.aiter_lines():
        line = raw_line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        if data:
            yield data
