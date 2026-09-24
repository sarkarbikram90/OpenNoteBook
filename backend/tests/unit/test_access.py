"""OpenNotebook — Unit tests for query-time access resolution and ACL visibility.

These tests model two users with different roles asking the "same" question and
assert they see different chunks — the core permission-aware retrieval guarantee.
"""

from __future__ import annotations

from typing import Any

from app.domain.governance.access import build_security_context, clearance_for_roles
from app.domain.retrieval.retriever import is_chunk_authorized

CHUNKS: list[dict[str, Any]] = [
    {"chunk_id": "public", "sensitivity_level": "public", "allowed_roles": [], "allowed_users": []},
    {"chunk_id": "internal", "sensitivity_level": "internal", "allowed_roles": [], "allowed_users": []},
    {
        "chunk_id": "confidential",
        "sensitivity_level": "confidential",
        "allowed_roles": [],
        "allowed_users": [],
    },
    {"chunk_id": "finance_only", "sensitivity_level": "internal", "allowed_roles": ["finance"], "allowed_users": []},
    {"chunk_id": "u1_only", "sensitivity_level": "internal", "allowed_roles": [], "allowed_users": ["u1"]},
]


def _visible(ctx: Any) -> set[str]:
    return {c["chunk_id"] for c in CHUNKS if is_chunk_authorized(c, ctx)}


def test_clearance_mapping():
    assert clearance_for_roles([]) == "internal"
    assert clearance_for_roles(["viewer"]) == "internal"
    assert clearance_for_roles(["member"]) == "confidential"
    assert clearance_for_roles(["admin"]) == "restricted"
    assert clearance_for_roles(["owner"]) == "restricted"
    # Highest clearance among the roles wins, regardless of order.
    assert clearance_for_roles(["viewer", "member"]) == "confidential"


def test_build_security_context_defaults_to_viewer():
    ctx = build_security_context("u1", [])
    assert ctx.user_id == "u1"
    assert ctx.roles == ["viewer"]
    assert ctx.max_sensitivity == "internal"


def test_viewer_is_blocked_from_confidential_and_restricted_chunks():
    viewer = build_security_context("u9", ["viewer"])
    visible = _visible(viewer)
    assert visible == {"public", "internal"}
    assert "confidential" not in visible
    assert "finance_only" not in visible
    assert "u1_only" not in visible


def test_finance_member_sees_more_than_viewer():
    finance = build_security_context("u1", ["finance", "member"])
    visible = _visible(finance)
    assert "confidential" in visible  # member clearance
    assert "finance_only" in visible  # role grant
    assert "u1_only" in visible  # explicit user grant


def test_two_users_with_different_groups_get_different_results():
    viewer = build_security_context("u9", ["viewer"])
    finance = build_security_context("u1", ["finance", "member"])
    assert _visible(viewer) != _visible(finance)
    assert _visible(viewer).isdisjoint({"finance_only", "u1_only", "confidential"})


def test_owner_sees_everything():
    owner = build_security_context("admin-1", ["owner"])
    assert _visible(owner) == {c["chunk_id"] for c in CHUNKS}
