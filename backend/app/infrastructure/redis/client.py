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

import socket
import time

logger = logging.getLogger(__name__)

_redis_checked_at: float = 0.0
_redis_available: bool | None = None


def is_redis_available(timeout: float = 0.3) -> bool:
    """Fast probe to determine whether Redis is reachable, cached for 60s."""
    global _redis_checked_at, _redis_available
    now = time.monotonic()
    if _redis_available is not None and (now - _redis_checked_at < 60.0):
        return _redis_available

    settings = get_settings()
    try:
        clean = (
            settings.redis_url.replace("redis://", "")
            .replace("rediss://", "")
            .split("/")[0]
        )
        if "@" in clean:
            clean = clean.split("@", 1)[1]
        if ":" in clean:
            host, port_str = clean.split(":", 1)
            port = int(port_str)
        else:
            host = clean
            port = 6379
        with socket.create_connection((host, port), timeout=timeout):
            _redis_available = True
    except Exception:
        _redis_available = False

    _redis_checked_at = now
    return _redis_available


def get_sync_redis() -> redis.Redis:
    """Return a synchronous Redis client (for use in Celery workers)."""
    settings = get_settings()
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )


def get_async_redis() -> aioredis.Redis:
    """Return an async Redis client (for use in FastAPI SSE endpoints)."""
    settings = get_settings()
    return aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )


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
    if not is_redis_available():
        return

    try:
        client = get_sync_redis()
        message = json.dumps({
            "source_id": source_id,
            "status": status,
            **(detail or {}),
        })
        client.publish(_channel_name(source_id), message)
        logger.debug("Published status %s for source %s", status, source_id)
    except Exception as exc:
        global _redis_available
        _redis_available = False
        logger.debug("Skipping Redis publish_status for source %s: %s", source_id, exc)


async def subscribe_status(source_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """Subscribe to status updates for a source (async generator for SSE).

    Yields parsed JSON dicts as they arrive on the channel.  The generator
    terminates when a ``READY`` or ``FAILED`` status is received.

    Args:
        source_id: The UUID of the source to track.

    Yields:
        Parsed status event dicts.
    """
    if not is_redis_available():
        return

    client = None
    try:
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
    except Exception as exc:
        logger.debug("Redis subscribe failed or closed for source %s: %s", source_id, exc)
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
