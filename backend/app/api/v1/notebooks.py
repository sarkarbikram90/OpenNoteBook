"""OpenNotebook — Notebook CRUD API endpoints.

Provides full CRUD for notebooks scoped to the authenticated user.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update, delete

from app.api.v1.schemas.notebooks import (
    NotebookCreate,
    NotebookListResponse,
    NotebookResponse,
    NotebookUpdate,
)
from app.core.deps import CurrentUser, DbSession
from app.infrastructure.db.models import Notebook, Source

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _notebook_to_response(notebook: Notebook, db: DbSession) -> NotebookResponse:
    """Convert a Notebook ORM model to a response schema with source count."""
    result = await db.execute(
        select(func.count()).where(Source.notebook_id == notebook.id)
    )
    source_count = result.scalar() or 0

    return NotebookResponse(
        id=notebook.id,
        name=notebook.name,
        description=notebook.description,
        source_count=source_count,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
    )


async def _get_user_notebook(notebook_id: uuid.UUID, user_id: uuid.UUID, db: DbSession) -> Notebook:
    """Fetch a notebook belonging to the current user or raise 404."""
    result = await db.execute(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == user_id,
        )
    )
    notebook = result.scalar_one_or_none()
    if notebook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )
    return notebook


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=NotebookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notebook",
)
async def create_notebook(
    body: NotebookCreate,
    user: CurrentUser,
    db: DbSession,
) -> NotebookResponse:
    """Create a new notebook for the authenticated user."""
    notebook = Notebook(
        user_id=user.id,
        name=body.name,
        description=body.description,
    )
    db.add(notebook)
    await db.flush()
    await db.refresh(notebook)
    return await _notebook_to_response(notebook, db)


@router.get(
    "",
    response_model=NotebookListResponse,
    summary="List notebooks",
)
async def list_notebooks(
    user: CurrentUser,
    db: DbSession,
) -> NotebookListResponse:
    """List all notebooks belonging to the authenticated user."""
    result = await db.execute(
        select(Notebook)
        .where(Notebook.user_id == user.id)
        .order_by(Notebook.updated_at.desc())
    )
    notebooks = list(result.scalars().all())

    responses = [await _notebook_to_response(nb, db) for nb in notebooks]
    return NotebookListResponse(notebooks=responses, total=len(responses))


@router.get(
    "/{notebook_id}",
    response_model=NotebookResponse,
    summary="Get a notebook",
)
async def get_notebook(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> NotebookResponse:
    """Retrieve a specific notebook by ID."""
    notebook = await _get_user_notebook(notebook_id, user.id, db)
    return await _notebook_to_response(notebook, db)


@router.patch(
    "/{notebook_id}",
    response_model=NotebookResponse,
    summary="Update a notebook",
)
async def update_notebook(
    notebook_id: uuid.UUID,
    body: NotebookUpdate,
    user: CurrentUser,
    db: DbSession,
) -> NotebookResponse:
    """Update a notebook's name and/or description."""
    notebook = await _get_user_notebook(notebook_id, user.id, db)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(notebook, field, value)

    await db.flush()
    await db.refresh(notebook)
    return await _notebook_to_response(notebook, db)


@router.delete(
    "/{notebook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a notebook",
)
async def delete_notebook(
    notebook_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a notebook and all its sources, sessions, and indexed data.

    Also cleans up Qdrant vectors and the BM25 index for the notebook.
    """
    notebook = await _get_user_notebook(notebook_id, user.id, db)

    # Clean up vector store and BM25 index (best-effort, don't block deletion)
    try:
        from app.infrastructure.qdrant.client import delete_by_notebook
        delete_by_notebook(str(notebook_id))
    except Exception:
        pass

    try:
        from app.infrastructure.redis.client import get_sync_redis
        redis_client = get_sync_redis()
        redis_client.delete(f"bm25:{notebook_id}")
        redis_client.delete(f"bm25_docs:{notebook_id}")
    except Exception:
        pass

    await db.execute(
        delete(Notebook).where(Notebook.id == notebook_id)
    )
