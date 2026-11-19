"""Unit tests for Workspaces RBAC helpers and schema validation."""

from __future__ import annotations

import pytest


def test_workspace_slugify_and_validation() -> None:
    """Verify workspace slug generation and Pydantic request validation."""
    pytest.importorskip("fastapi")
    from app.api.v1.workspaces import (
        WorkspaceCreateRequest,
        WorkspaceMemberCreateRequest,
        _slugify,
    )

    assert _slugify("Platform Engineering Team!") == "platform-engineering-team"
    assert _slugify("   ").startswith("ws-")

    req = WorkspaceCreateRequest(
        name="Security Ops",
        enable_pii_redaction=True,
        default_sensitivity="confidential",
    )
    assert req.name == "Security Ops"
    assert req.default_sensitivity == "confidential"

    member_req = WorkspaceMemberCreateRequest(email="alice@acme.com", role="admin")
    assert member_req.email == "alice@acme.com"
    assert member_req.role == "admin"
