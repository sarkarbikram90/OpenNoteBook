"""OpenNotebook — Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    summary="Application health check",
    response_model=dict[str, str],
)
async def health() -> dict[str, str]:
    """Return a simple health check response.

    Used by Docker HEALTHCHECK, load balancers, and monitoring.
    """
    return {"status": "ok"}


@router.get(
    "/diag",
    summary="Application database diagnostics",
)
async def diag() -> dict[str, object]:
    """Diagnostic endpoint to inspect active database host, port, and connectivity."""
    import urllib.parse
    from sqlalchemy import text
    from app.core.config import get_settings
    from app.infrastructure.db.session import async_engine

    s = get_settings()
    parsed = urllib.parse.urlsplit(s.database_url)
    db_ok = False
    db_err = None
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        db_err = f"{type(exc).__name__}: {exc}"

    return {
        "host": parsed.hostname,
        "port": parsed.port,
        "user": parsed.username,
        "db_ok": db_ok,
        "db_err": db_err,
    }
