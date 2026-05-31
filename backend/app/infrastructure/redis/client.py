"""OpenNotebook — Redis client for SSE status pub/sub.

Provides publish/subscribe helpers so Celery workers can broadcast
source processing status updates that the SSE endpoint streams to
the frontend in real time.

Channel pattern: ``source_status:{source_id}``
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import redis
import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_sync_redis() -> redis.Redis:
    """Return a synchronous Redis client (for use in Celery workers)."""
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def get_async_redis() -> aioredis.Redis:
    """Return an async Redis client (for use in FastAPI SSE endpoints)."""
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _channel_name(source_id: str) -> str:
    """Build the pub/sub channel name for a source."""
    return f"source_status:{source_id}"


def publish_status(source_id: str, status: str, detail: dict[str, Any] | None = None) -> None:
    """Publish a status update for a source (called from Celery workers).

    Args:
        source_id: The UUID of the source being processed.
        status: The new status (e.g. EXTRACTING, CHUNKING, EMBEDDING, READY, FAILED).
        detail: Optional extra detail dict (progress percentage, error message, etc.).
    """
    client = get_sync_redis()
    message = json.dumps({
        "source_id": source_id,
        "status": status,
        **(detail or {}),
    })
    client.publish(_channel_name(source_id), message)
    logger.debug("Published status %s for source %s", status, source_id)


async def subscribe_status(source_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """Subscribe to status updates for a source (async generator for SSE).

    Yields parsed JSON dicts as they arrive on the channel.  The generator
    terminates when a ``READY`` or ``FAILED`` status is received.

    Args:
        source_id: The UUID of the source to track.

    Yields:
        Parsed status event dicts.
    """
    client = get_async_redis()
    pubsub = client.pubsub()
    channel = _channel_name(source_id)

    await pubsub.subscribe(channel)
    logger.debug("SSE subscribed to channel: %s", channel)

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message is not None and message["type"] == "message":
                data = json.loads(message["data"])
                yield data

                # Terminal statuses — close the stream
                if data.get("status") in ("READY", "FAILED"):
                    break
            else:
                # Yield control to the event loop while waiting
                await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await client.aclose()
