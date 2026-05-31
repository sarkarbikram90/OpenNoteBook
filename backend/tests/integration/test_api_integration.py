"""OpenNotebook — API Integration Tests.

Validates core system features:
1. User Registration, Login, Token Refresh, and Logout flow.
2. Notebook CRUD.
3. Document Ingestion flow (mock upload + status checking).
4. SSE Chat Streaming with citations.
"""

from __future__ import annotations

import json
import uuid
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure these client modules are loaded before patching, preventing AttributeError on lookup
import app.infrastructure.minio.client
import app.infrastructure.ollama.client
import app.infrastructure.qdrant.client
from app.main import app
from app.core.deps import get_db, get_current_user

client = TestClient(app)


class SmartMockDb(AsyncMock):
    """A customized mock database session class.
    
    Prevents unawaited coroutine warnings by providing synchronous standard MagicMocks
    for synchronous DB methods (e.g. `add`, `delete`), dynamically populating UUIDs
    and datetimes on flush/refresh, and routing execute queries logically based on the query target.
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.added_objects = []

        def mock_add(instance: any) -> None:
            self.added_objects.append(instance)

        self.add = MagicMock(side_effect=mock_add)
        self.delete = MagicMock()
        self.mock_user = None
        self.mock_notebook = None
        self.mock_session = None
        self.mock_source = None

        async def mock_flush(*args: any, **kwargs: any) -> None:
            for instance in self.added_objects:
                if hasattr(instance, "id") and getattr(instance, "id", None) is None:
                    instance.id = uuid.uuid4()
                if hasattr(instance, "created_at") and getattr(instance, "created_at", None) is None:
                    instance.created_at = datetime.datetime.now(datetime.timezone.utc)
                if hasattr(instance, "updated_at") and getattr(instance, "updated_at", None) is None:
                    instance.updated_at = datetime.datetime.now(datetime.timezone.utc)

        async def mock_refresh(instance: any, *args: any, **kwargs: any) -> None:
            if hasattr(instance, "id") and getattr(instance, "id", None) is None:
                instance.id = uuid.uuid4()
            if hasattr(instance, "created_at") and getattr(instance, "created_at", None) is None:
                instance.created_at = datetime.datetime.now(datetime.timezone.utc)
            if hasattr(instance, "updated_at") and getattr(instance, "updated_at", None) is None:
                instance.updated_at = datetime.datetime.now(datetime.timezone.utc)

        self.flush.side_effect = mock_flush
        self.refresh.side_effect = mock_refresh

        async def mock_execute(query: any, *args: any, **kwargs: any) -> MagicMock:
            query_str = str(query).lower()
            res = MagicMock()
            
            if "count" in query_str:
                res.scalar.return_value = 0
                res.scalar_one_or_none.return_value = 0
            elif "notebook" in query_str:
                res.scalar_one_or_none.return_value = self.mock_notebook
                res.scalars.return_value.all.return_value = [self.mock_notebook] if self.mock_notebook else []
            elif "chatsession" in query_str or "session" in query_str:
                res.scalar_one_or_none.return_value = self.mock_session
            elif "user" in query_str:
                res.scalar_one_or_none.return_value = self.mock_user
            elif "source" in query_str:
                res.scalar_one_or_none.return_value = self.mock_source
                res.scalars.return_value.all.return_value = [self.mock_source] if self.mock_source else []
                
            return res

        self.execute.side_effect = mock_execute


@pytest.fixture(autouse=True)
def clean_dependency_overrides() -> None:
    """Ensure FastAPI dependency overrides are cleared before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


# ── 1. Auth Flow Integration Tests ──────────────────────────────────────────

@patch("app.api.v1.auth.hash_password")
@patch("app.api.v1.auth.create_access_token")
@patch("app.api.v1.auth.create_refresh_token")
def test_auth_registration_and_login_flow(
    mock_create_refresh: MagicMock,
    mock_create_access: MagicMock,
    mock_hash_pw: MagicMock,
) -> None:
    """Validate registration, login, profile, and token refresh endpoints."""
    mock_hash_pw.return_value = "hashed_password_123"
    mock_create_access.return_value = "access_token_val"
    mock_create_refresh.return_value = "refresh_token_val"

    # Setup database mock and overrides
    mock_db = SmartMockDb()
    app.dependency_overrides[get_db] = lambda: mock_db

    # 1a. User Registration
    mock_db.mock_user = None  # No existing user
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["access_token"] == "access_token_val"
    assert data["refresh_token"] == "refresh_token_val"

    # 1b. User Login
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "newuser@example.com"
    mock_user.password_hash = "hashed_password_123"
    mock_user.is_active = True
    
    mock_db.mock_user = mock_user

    with patch("app.api.v1.auth.verify_password", return_value=True):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "newuser@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access_token_val"
        assert data["refresh_token"] == "refresh_token_val"

    # 1c. Token Refresh
    mock_payload = MagicMock()
    mock_payload.type = "refresh"
    mock_payload.sub = str(mock_user.id)
    mock_payload.jti = "jti_token_id"

    with patch("app.api.v1.auth.decode_token", return_value=mock_payload), \
         patch("app.api.v1.auth.revoke_token") as mock_revoke:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "refresh_token_val"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access_token_val"
        assert data["refresh_token"] == "refresh_token_val"
        mock_revoke.assert_called_once_with("jti_token_id")

    # 1d. User Logout
    app.dependency_overrides[get_current_user] = lambda: mock_user
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer access_token_val"},
    )
    assert response.status_code == 204


# ── 2. Notebook CRUD Integration Tests ──────────────────────────────────────

@patch("app.infrastructure.qdrant.client.delete_by_notebook")
def test_notebook_crud_lifecycle(mock_delete_qdrant: MagicMock) -> None:
    """Validate Create, Read, Update, and Delete endpoints for Notebooks."""
    mock_delete_qdrant.return_value = None
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    
    notebook_id = uuid.uuid4()
    mock_notebook = MagicMock()
    mock_notebook.id = notebook_id
    mock_notebook.name = "My Research Notebook"
    mock_notebook.description = "A notebook for AI agents"
    mock_notebook.created_at = datetime.datetime.now(datetime.timezone.utc)
    mock_notebook.updated_at = datetime.datetime.now(datetime.timezone.utc)

    # Setup database mock and overrides
    mock_db = SmartMockDb()
    mock_db.mock_user = mock_user
    mock_db.mock_notebook = mock_notebook

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # 2a. Create Notebook
    response = client.post(
        "/api/v1/notebooks",
        json={"name": "My Research Notebook", "description": "A notebook for AI agents"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Research Notebook"
    assert data["description"] == "A notebook for AI agents"

    # 2b. Read Notebooks
    response = client.get("/api/v1/notebooks")
    assert response.status_code == 200
    data = response.json()
    assert len(data["notebooks"]) == 1
    assert data["notebooks"][0]["name"] == "My Research Notebook"

    # 2c. Read Single Notebook
    response = client.get(f"/api/v1/notebooks/{notebook_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "My Research Notebook"

    # 2d. Update Notebook
    response = client.patch(
        f"/api/v1/notebooks/{notebook_id}",
        json={"name": "Updated Notebook Name"},
    )
    assert response.status_code == 200

    # 2e. Delete Notebook
    response = client.delete(f"/api/v1/notebooks/{notebook_id}")
    assert response.status_code == 204


# ── 3. Document Ingestion Pipeline Tests ────────────────────────────────────

@patch("app.infrastructure.minio.client.upload_file")
@patch("app.worker.tasks.process_source.process_source")
def test_document_ingestion_and_status(
    mock_process_source: MagicMock,
    mock_upload_file: MagicMock,
) -> None:
    """Validate upload endpoint registers document and initializes processing status."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    
    notebook_id = uuid.uuid4()
    source_id = uuid.uuid4()
    
    mock_notebook = MagicMock()
    mock_notebook.id = notebook_id
    mock_notebook.user_id = mock_user.id
    
    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.notebook_id = notebook_id
    mock_source.name = "research_paper.pdf"
    mock_source.source_type = "pdf"
    mock_source.status = "PENDING"
    mock_source.created_at = datetime.datetime.now(datetime.timezone.utc)
    mock_source.updated_at = datetime.datetime.now(datetime.timezone.utc)
    mock_source.metadata = {}

    # Setup database mock and overrides
    mock_db = SmartMockDb()
    mock_db.mock_user = mock_user
    mock_db.mock_notebook = mock_notebook
    mock_db.mock_source = mock_source

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # Perform mock multipart upload
    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/sources/upload",
        files={"file": ("research_paper.pdf", b"pdf binary content", "application/pdf")},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["source_id"] is not None
    
    # Verify background task processing triggered
    mock_process_source.delay.assert_called_once()


# ── 4. RAG Chat & SSE Citations Tests ────────────────────────────────────────

@patch("app.domain.retrieval.retriever.retrieve")
@patch("app.infrastructure.ollama.client.stream_generate")
def test_rag_chat_sse_stream_and_citations(
    mock_stream_generate: MagicMock,
    mock_retrieve: MagicMock,
) -> None:
    """Validate chat SSE stream generates token outputs and appends citation metadata."""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    
    notebook_id = uuid.uuid4()
    session_id = uuid.uuid4()
    
    mock_notebook = MagicMock()
    mock_notebook.id = notebook_id
    mock_notebook.user_id = mock_user.id

    mock_session = MagicMock()
    mock_session.id = session_id
    mock_session.notebook_id = notebook_id

    # Setup database mock and overrides
    mock_db = SmartMockDb()
    mock_db.mock_user = mock_user
    mock_db.mock_notebook = mock_notebook
    mock_db.mock_session = mock_session

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # Mock Retriever results
    from app.domain.retrieval.retriever import RetrievalResult, RetrievedChunk
    chunk_id = str(uuid.uuid4())
    mock_chunk = RetrievedChunk(
        chunk_id=chunk_id,
        source_id="src_id",
        source_name="transformers.pdf",
        notebook_id=str(notebook_id),
        text="The Transformer relies on attention mechanisms [Source 1].",
        page=1,
        section="Introduction",
        relevance_score=0.98
    )
    mock_retrieve.return_value = RetrievalResult(
        chunks=[mock_chunk],
        dense_latency_ms=10.0,
        bm25_latency_ms=5.0,
        fusion_latency_ms=1.0,
        rerank_latency_ms=20.0,
        total_latency_ms=36.0
    )

    # Mock Ollama generator
    async def mock_generator(prompt: str) -> any:
        yield " The"
        yield " transformer"
        yield " uses"
        yield " attention"
        yield " [Source 1]."
    
    mock_stream_generate.side_effect = mock_generator

    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/chat",
        json={"question": "What does a transformer rely on?"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    # Parse SSE events from response stream
    events = []
    for line in response.iter_lines():
        if line:
            line_str = line.decode("utf-8") if hasattr(line, "decode") else line
            events.append(line_str)

    # Verify token and citation stream payloads
    assert any("event: token" in ev for ev in events)
    assert any("event: citation" in ev for ev in events)
    assert any("event: done" in ev for ev in events)
