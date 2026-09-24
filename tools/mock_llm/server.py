"""OpenNotebook — Deterministic mock LLM server (Ollama-compatible).

Purpose: provide a stable, offline stand-in for Ollama so that integration
tests, CI, and local development do not depend on downloading or running a real
model. It implements the subset of the Ollama REST API that the application uses:

    POST /api/generate   text generation (streaming and non-streaming)
    GET  /api/tags       list available models
    GET  /               liveness probe

The output is deterministic: the same prompt always yields the same answer, which
contains an inline citation marker so citation handling can be asserted.

Configuration (environment variables):
    MOCK_LLM_MODEL      model name reported and accepted (default: mock-llama3)
    MOCK_LLM_ANSWER     the deterministic answer text (default: a grounded reply)
    MOCK_LLM_DELAY_MS   per-token delay in ms, to simulate streaming (default: 0)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

MODEL = os.getenv("MOCK_LLM_MODEL", "mock-llama3")
ANSWER = os.getenv(
    "MOCK_LLM_ANSWER",
    "Based on the provided sources, this is a deterministic mock answer. [Source 1]",
)
DELAY_MS = int(os.getenv("MOCK_LLM_DELAY_MS", "0"))

app = FastAPI(title="OpenNotebook Mock LLM", version="0.1.0")


@app.get("/")
async def root() -> JSONResponse:
    """Liveness probe mirroring Ollama's root behaviour."""
    return JSONResponse({"status": "ok", "model": MODEL})


@app.get("/api/tags")
async def tags() -> JSONResponse:
    """List available models (Ollama-compatible shape)."""
    return JSONResponse(
        {
            "models": [
                {
                    "name": MODEL,
                    "model": MODEL,
                    "modified_at": "2026-01-01T00:00:00Z",
                    "size": 0,
                    "digest": "mock",
                }
            ]
        }
    )


async def _tokens(text: str) -> list[str]:
    """Split the answer into word-ish tokens preserving spacing for realism."""
    return [f"{w} " for w in text.split(" ")]


@app.post("/api/generate")
async def generate(request: Request) -> Any:
    """Generate a deterministic response, streaming or single-shot."""
    body: dict[str, Any] = await request.json()
    model = body.get("model", MODEL)
    stream = bool(body.get("stream", True))
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not stream:
        return JSONResponse(
            {
                "model": model,
                "created_at": created_at,
                "response": ANSWER,
                "done": True,
                "done_reason": "stop",
            }
        )

    async def event_stream() -> AsyncGenerator[str, None]:
        for token in await _tokens(ANSWER):
            chunk = {
                "model": model,
                "created_at": created_at,
                "response": token,
                "done": False,
            }
            yield json.dumps(chunk) + "\n"
            if DELAY_MS:
                await asyncio.sleep(DELAY_MS / 1000.0)
        yield json.dumps(
            {"model": model, "created_at": created_at, "response": "", "done": True,
             "done_reason": "stop"}
        ) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
