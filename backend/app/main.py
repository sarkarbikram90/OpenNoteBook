"""OpenNotebook API — FastAPI application entry point.

Configures CORS, registers routers, and manages the application lifespan.
On startup, ensures MinIO bucket and Qdrant collection exist.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.notebooks import router as notebooks_router
from app.api.v1.search import router as search_router
from app.api.v1.settings import router as settings_router
from app.api.v1.sources import router as sources_router
from app.core.config import get_settings
from app.core.logging import init_tracing, setup_logging
from app.infrastructure.db.session import async_engine

# Initialize logging and OpenTelemetry tracing
setup_logging()
init_tracing("api")

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # ── Startup ─────────────────────────────────────────────────────────
    # Instrument SQLAlchemy
    try:
        SQLAlchemyInstrumentor().instrument(engine=async_engine.sync_engine)
        logger.info("SQLAlchemy engine instrumented with OpenTelemetry")
    except Exception as e:
        logger.warning("SQLAlchemy instrumentation failed: %s", e)

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

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# ── CORS Middleware ──────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Prometheus Request Monitoring Middleware ───────────────────────────

@app.middleware("http")
async def monitor_requests(request: Request, call_next: Any) -> Response:
    """Middleware to measure and record API request duration metrics."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    # Use the matched route template path (e.g. /api/v1/notebooks/{id}) if available
    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path

    # Track metrics
    from app.core.metrics import api_request_duration
    api_request_duration.labels(
        endpoint=endpoint,
        method=request.method,
        status=response.status_code,
    ).observe(duration)

    return response


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


# ── Metrics Endpoint ────────────────────────────────────────────────────────

@app.get(f"{API_V1_PREFIX}/metrics")
def metrics() -> Response:
    """Endpoint serving Prometheus formatted metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

