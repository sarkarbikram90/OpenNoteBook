"""OpenNotebook — Async Ollama LLM client.

Provides streaming and non-streaming inference via the Ollama REST API.
Uses ``httpx`` for async HTTP with configurable timeouts.

Endpoints used:
    POST /api/generate  — text generation (streaming + non-streaming)
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Long timeout for LLM generation (models can take a while on CPU)
_GENERATE_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


async def stream_generate(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
) -> AsyncGenerator[str, None]:
    """Stream tokens from the Ollama generate endpoint.

    Connects to Ollama and yields individual token strings as they
    are produced by the model.  The caller is responsible for
    assembling the full response.

    Args:
        prompt: The full prompt string (system + context + question).
        model: LLM model name.  Defaults to ``settings.ollama_model``.
        temperature: Sampling temperature.  Defaults to ``settings.ollama_temperature``.

    Yields:
        Individual token strings from the model.
    """
    settings = get_settings()
    model = model or settings.ollama_model
    temperature = temperature if temperature is not None else settings.ollama_temperature

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
        },
    }

    url = f"{settings.ollama_url}/api/generate"
    logger.info("Streaming LLM generation: model=%s, prompt_len=%d", model, len(prompt))

    async with httpx.AsyncClient(timeout=_GENERATE_TIMEOUT) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping non-JSON line from Ollama: %s", line[:100])
                    continue

                token = data.get("response", "")
                if token:
                    yield token

                # Ollama signals completion with done=true
                if data.get("done", False):
                    logger.debug(
                        "Ollama generation complete: total_duration=%s",
                        data.get("total_duration"),
                    )
                    return


async def generate(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """Non-streaming text generation via Ollama.

    Collects the full response and returns it as a single string.
    Used for summarisation and other non-interactive tasks.

    Args:
        prompt: The full prompt string.
        model: LLM model name.  Defaults to ``settings.ollama_model``.
        temperature: Sampling temperature.

    Returns:
        The complete generated text.
    """
    settings = get_settings()
    model = model or settings.ollama_model
    temperature = temperature if temperature is not None else settings.ollama_temperature

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    url = f"{settings.ollama_url}/api/generate"
    logger.info("Non-streaming LLM generation: model=%s, prompt_len=%d", model, len(prompt))

    async with httpx.AsyncClient(timeout=_GENERATE_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    result = data.get("response", "")
    logger.info("Generation complete: response_len=%d", len(result))
    return result
