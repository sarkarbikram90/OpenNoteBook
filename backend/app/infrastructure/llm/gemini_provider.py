"""OpenNotebook — Google Gemini LLM provider (streaming generateContent)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.infrastructure.llm.base import BaseLLMProvider, iter_sse_data

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Provider for the Google Generative Language API (streaming)."""

    name = "gemini"

    def __init__(self, client: Any | None = None) -> None:
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.base_url = settings.gemini_base_url.rstrip("/")
        self.default_model = settings.gemini_model
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
        url = f"{self.base_url}/v1beta/models/{model}:streamGenerateContent"
        try:
            async with client.stream(
                "POST",
                url,
                params={"alt": "sse", "key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature if temperature is not None else 0.1
                    },
                },
            ) as response:
                response.raise_for_status()
                async for data in iter_sse_data(response):
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for candidate in payload.get("candidates", []):
                        for part in candidate.get("content", {}).get("parts", []):
                            text = part.get("text")
                            if text:
                                yield text
        finally:
            if owned:
                await client.aclose()
