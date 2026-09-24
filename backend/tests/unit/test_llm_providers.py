"""OpenNotebook — Unit tests for pluggable LLM providers and feedback schema."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.infrastructure.llm import OllamaProvider, get_llm_provider
from app.infrastructure.llm.anthropic_provider import AnthropicProvider
from app.infrastructure.llm.gemini_provider import GeminiProvider
from app.infrastructure.llm.openai_provider import OpenAIProvider


def _async_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_factory_defaults_to_ollama():
    assert isinstance(get_llm_provider("ollama"), OllamaProvider)


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_llm_provider("does-not-exist")


async def test_openai_provider_streams_and_aggregates():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers.get("authorization", "").startswith("Bearer ")
        body = (
            'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, content=body.encode())

    client = _async_client(handler)
    try:
        provider = OpenAIProvider(client=client)
        tokens = [t async for t in provider.stream_generate("hi")]
        assert "".join(tokens) == "Hello world"
        assert await provider.generate("hi") == "Hello world"
    finally:
        await client.aclose()


async def test_anthropic_provider_streams_content_block_deltas():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/messages")
        assert request.headers.get("x-api-key") is not None
        body = (
            'event: content_block_delta\n'
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Bonjour"}}\n\n'
            'event: message_stop\n'
            'data: {"type":"message_stop"}\n\n'
        )
        return httpx.Response(200, content=body.encode())

    client = _async_client(handler)
    try:
        provider = AnthropicProvider(client=client)
        assert await provider.generate("hi") == "Bonjour"
    finally:
        await client.aclose()


async def test_gemini_provider_streams_candidate_parts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert ":streamGenerateContent" in request.url.path
        body = (
            'data: {"candidates":[{"content":{"parts":[{"text":"Guten "}]}}]}\n\n'
            'data: {"candidates":[{"content":{"parts":[{"text":"Tag"}]}}]}\n\n'
        )
        return httpx.Response(200, content=body.encode())

    client = _async_client(handler)
    try:
        provider = GeminiProvider(client=client)
        assert await provider.generate("hi") == "Guten Tag"
    finally:
        await client.aclose()


def test_feedback_request_validates_rating():
    from pydantic import ValidationError

    from app.api.v1.schemas.chat import FeedbackRequest

    FeedbackRequest(message_id=uuid.uuid4(), rating="up")
    with pytest.raises(ValidationError):
        FeedbackRequest(message_id=uuid.uuid4(), rating="maybe")
