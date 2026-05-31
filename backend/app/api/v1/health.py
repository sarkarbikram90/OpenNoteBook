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
