"""OpenNotebook — OpenAI (and OpenAI-compatible) LLM provider."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.infrastructure.llm.base import BaseLLMProvider, iter_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """Provider for the OpenAI Chat Completions API (streaming)."""

    name = "openai"

    def __init__(self, client: Any | None = None) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url.rstrip("/")
        self.default_model = settings.openai_model
        self._client = client

    async def stream_generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        import httpx

        model = model or self.default_model
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=120.0)
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature if temperature is not None else 0.1,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for data in iter_sse_data(response):
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in payload.get("choices", []):
                        content = choice.get("delta", {}).get("content")
                        if content:
                            yield content
        finally:
            if owned:
                await client.aclose()
