"""OpenNotebook API — FastAPI application entry point.

Configures CORS, registers routers, and manages the application lifespan.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.settings import router as settings_router
from app.core.config import get_settings
from app.infrastructure.db.session import async_engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # Startup — nothing to do (engine is created lazily)
    yield
    # Shutdown — dispose of the async engine connection pool
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
