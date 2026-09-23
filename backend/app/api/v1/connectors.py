"""OpenNotebook — Enterprise Connectors API endpoints.

Provides:
- Create and configure enterprise connectors (Web, S3, etc.)
- List active connectors
- Test connection
- Trigger synchronization
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.audit import record_audit_event
from app.domain.connectors.web import WebConnector
from app.domain.connectors.s3_connector import S3BucketConnector
from app.infrastructure.db.models import ConnectorConfig, Notebook, Source, WorkspaceMember

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connectors", tags=["connectors"])


# ── Schemas ─────────────────────────────────────────────────────────────────


class ConnectorCreateRequest(BaseModel):
    workspace_id: uuid.UUID
    notebook_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=120)
    connector_type: str = Field(..., description="'web' or 's3'")
    config_json: dict[str, Any] = Field(default_factory=dict)
    schedule_cron: str | None = None


class ConnectorResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    notebook_id: uuid.UUID | None
    name: str
    connector_type: str
    status: str
    last_sync_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class ConnectorTestResponse(BaseModel):
    success: bool
    message: str


class ConnectorSyncResponse(BaseModel):
    connector_id: uuid.UUID
    documents_synced: int
    status: str


# ── Helper ──────────────────────────────────────────────────────────────────


async def _verify_workspace_permission(workspace_id: uuid.UUID, user_id: uuid.UUID, db: DbSession) -> str:
    """Ensure user is an admin or owner of the workspace."""
    result = await db.execute(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    role = result.scalar_one_or_none()
    if role is None or role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required for connector management",
        )
    return role


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=ConnectorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an enterprise connector",
)
async def create_connector(
    payload: ConnectorCreateRequest,
    user: CurrentUser,
    db: DbSession,
) -> ConnectorResponse:
    """Register a new enterprise data connector."""
    await _verify_workspace_permission(payload.workspace_id, user.id, db)

    connector = ConnectorConfig(
        workspace_id=payload.workspace_id,
        notebook_id=payload.notebook_id,
        name=payload.name,
        connector_type=payload.connector_type.lower(),
        config_json=payload.config_json,
        schedule_cron=payload.schedule_cron,
        status="ACTIVE",
    )
    db.add(connector)
    await db.flush()

    await record_audit_event(
        db=db,
        action="connector.create",
        resource_type="connector",
        resource_id=str(connector.id),
        user_id=user.id,
        details={"name": payload.name, "type": payload.connector_type},
    )

    return ConnectorResponse.model_validate(connector)


@router.get(
    "",
    response_model=list[ConnectorResponse],
    summary="List enterprise connectors",
)
async def list_connectors(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[ConnectorResponse]:
    """List all connectors configured for a workspace."""
    # Verify user is at least a member of the workspace
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    res = await db.execute(
        select(ConnectorConfig)
        .where(ConnectorConfig.workspace_id == workspace_id)
        .order_by(ConnectorConfig.created_at.desc())
    )
    connectors = res.scalars().all()
    return [ConnectorResponse.model_validate(c) for c in connectors]


@router.post(
    "/{connector_id}/test",
    response_model=ConnectorTestResponse,
    summary="Test connector connectivity",
)
async def test_connector(
    connector_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> ConnectorTestResponse:
    """Test connection credentials and reachability."""
    result = await db.execute(
        select(ConnectorConfig).where(ConnectorConfig.id == connector_id)
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    await _verify_workspace_permission(connector.workspace_id, user.id, db)

    try:
        if connector.connector_type == "web":
            conn = WebConnector(connector.config_json)
            conn.test_connection()
        elif connector.connector_type == "s3":
            conn = S3BucketConnector(connector.config_json)
            conn.test_connection()
        else:
            raise ValueError(f"Unsupported connector type: {connector.connector_type}")

        return ConnectorTestResponse(success=True, message="Connection successful")
    except Exception as exc:
        return ConnectorTestResponse(success=False, message=str(exc))


@router.post(
    "/{connector_id}/sync",
    response_model=ConnectorSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger connector sync",
)
async def sync_connector(
    connector_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> ConnectorSyncResponse:
    """Execute connector sync and ingest discovered documents into the Data Lake."""
    result = await db.execute(
        select(ConnectorConfig).where(ConnectorConfig.id == connector_id)
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    await _verify_workspace_permission(connector.workspace_id, user.id, db)

    if not connector.notebook_id:
        raise HTTPException(
            status_code=400,
            detail="Connector must be associated with a target notebook to ingest documents",
        )

    # Instantiate connector
    if connector.connector_type == "web":
        conn = WebConnector(connector.config_json)
    elif connector.connector_type == "s3":
        conn = S3BucketConnector(connector.config_json)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported connector type: {connector.connector_type}")

    from app.infrastructure.storage.service import get_storage_service, StorageService
    from app.worker.tasks.process_source import process_source

    storage = get_storage_service()
    docs = conn.sync()

    for doc in docs:
        source_id = uuid.uuid4()
        raw_bytes = doc.content if isinstance(doc.content, bytes) else doc.content.encode("utf-8")
        clean_title = doc.title.replace(" ", "_").replace("/", "_")
        filename = f"{clean_title}.{doc.source_type}" if not clean_title.endswith(f".{doc.source_type}") else clean_title
        storage_path = f"sources/{source_id}/{filename}"

        storage.upload_raw_document(
            data=raw_bytes,
            object_name=storage_path,
            content_type="text/plain" if doc.source_type in ("txt", "md", "url") else "application/octet-stream",
        )
        file_hash = StorageService.calculate_file_hash(raw_bytes)

        source = Source(
            id=source_id,
            notebook_id=connector.notebook_id,
            name=doc.title,
            source_type=doc.source_type,
            source_url=doc.url,
            storage_path=storage_path,
            storage_type=storage.provider,
            status="PENDING",
            metadata_={"sha256": file_hash, "size_bytes": len(raw_bytes), "connector_id": str(connector_id)},
        )
        db.add(source)
        await db.flush()

        # Queue processing task
        process_source.delay(str(source_id))

    connector.last_sync_at = datetime.now(UTC)
    connector.status = "ACTIVE"
    connector.error_message = None
    await db.flush()

    await record_audit_event(
        db=db,
        action="connector.sync",
        resource_type="connector",
        resource_id=str(connector.id),
        user_id=user.id,
        details={"documents_synced": len(docs)},
    )

    return ConnectorSyncResponse(
        connector_id=connector.id,
        documents_synced=len(docs),
        status="ACTIVE",
    )
