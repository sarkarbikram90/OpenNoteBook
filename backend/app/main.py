"""OpenNotebook API — FastAPI application entry point.

Configures CORS, registers routers, and manages the application lifespan.
On startup, ensures MinIO bucket and Qdrant collection exist.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.notebooks import router as notebooks_router
from app.api.v1.search import router as search_router
from app.api.v1.settings import router as settings_router
from app.api.v1.sources import router as sources_router
from app.core.config import get_settings
from app.infrastructure.db.session import async_engine

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # ── Startup ─────────────────────────────────────────────────────────
    # Ensure MinIO bucket exists
    try:
        from app.infrastructure.minio.client import ensure_bucket
        ensure_bucket()
        logger.info("MinIO bucket ensured")
    except Exception as e:
        logger.warning("MinIO bucket init failed (may not be available yet): %s", e)

    # Ensure Qdrant collection exists
    try:
        from app.infrastructure.qdrant.client import ensure_collection
        ensure_collection()
        logger.info("Qdrant collection ensured")
    except Exception as e:
        logger.warning("Qdrant collection init failed (may not be available yet): %s", e)

    yield

    # ── Shutdown ────────────────────────────────────────────────────────
    await async_engine.dispose()


app = FastAPI(
    title="OpenNotebook API",
    description="Your private, open-source AI research assistant.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route Registration ──────────────────────────────────────────────────────

API_V1_PREFIX = "/api/v1"

app.include_router(health_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(settings_router, prefix=API_V1_PREFIX)
app.include_router(notebooks_router, prefix=API_V1_PREFIX)
app.include_router(sources_router, prefix=API_V1_PREFIX)
app.include_router(chat_router, prefix=API_V1_PREFIX)
app.include_router(search_router, prefix=API_V1_PREFIX)
app.include_router(jobs_router, prefix=API_V1_PREFIX)
