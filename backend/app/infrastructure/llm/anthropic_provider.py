"""OpenNotebook — Anthropic Claude LLM provider (streaming Messages API)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.infrastructure.llm.base import BaseLLMProvider, iter_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Provider for the Anthropic Messages API (streaming)."""

    name = "anthropic"

    def __init__(self, client: Any | None = None) -> None:
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        self.base_url = settings.anthropic_base_url.rstrip("/")
        self.default_model = settings.anthropic_model
        self.max_tokens = settings.anthropic_max_tokens
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
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": self.max_tokens,
                    "temperature": temperature if temperature is not None else 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for data in iter_sse_data(response):
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if payload.get("type") == "content_block_delta":
                        text = payload.get("delta", {}).get("text")
                        if text:
                            yield text
        finally:
            if owned:
                await client.aclose()
