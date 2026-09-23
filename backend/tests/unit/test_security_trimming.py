"""OpenNotebook — Unit tests for pre-retrieval Security Trimming and ACL isolation."""

from __future__ import annotations

import pytest

from app.domain.governance.sensitivity import SensitivityLevel
from app.domain.retrieval.retriever import UserSecurityContext, is_chunk_authorized


def test_sensitivity_level_hierarchy():
    """Verify clearance ranks properly enforce access boundaries."""
    assert SensitivityLevel.PUBLIC.is_accessible_by("public") is True
    assert SensitivityLevel.PUBLIC.is_accessible_by("internal") is True
    assert SensitivityLevel.INTERNAL.is_accessible_by("public") is False
    assert SensitivityLevel.CONFIDENTIAL.is_accessible_by("internal") is False
    assert SensitivityLevel.CONFIDENTIAL.is_accessible_by("confidential") is True
    assert SensitivityLevel.RESTRICTED.is_accessible_by("confidential") is False
    assert SensitivityLevel.RESTRICTED.is_accessible_by("restricted") is True


def test_admin_and_owner_have_full_access():
    """Owners and Admins bypass chunk restrictions for compliance and audit oversight."""
    admin_ctx = UserSecurityContext(
        user_id="admin-123",
        roles=["admin"],
        max_sensitivity="restricted",
    )
    owner_ctx = UserSecurityContext(
        user_id="owner-456",
        roles=["owner"],
        max_sensitivity="restricted",
    )

    restricted_chunk = {
        "chunk_id": "c1",
        "sensitivity_level": "restricted",
        "allowed_roles": ["hr_exec"],
        "allowed_users": ["special-user"],
    }

    assert is_chunk_authorized(restricted_chunk, admin_ctx) is True
    assert is_chunk_authorized(restricted_chunk, owner_ctx) is True


def test_viewer_blocked_from_confidential_chunk():
    """A standard viewer without clearance cannot retrieve confidential documents."""
    viewer_ctx = UserSecurityContext(
        user_id="viewer-1",
        roles=["viewer"],
        max_sensitivity="internal",
    )
    confidential_chunk = {
        "chunk_id": "c2",
        "sensitivity_level": "confidential",
        "allowed_roles": ["finance"],
    }

    assert is_chunk_authorized(confidential_chunk, viewer_ctx) is False


def test_role_based_acl_filtering():
    """A user with the matching role is granted access."""
    finance_ctx = UserSecurityContext(
        user_id="user-fin",
        roles=["finance_analyst", "member"],
        max_sensitivity="confidential",
    )
    hr_ctx = UserSecurityContext(
        user_id="user-hr",
        roles=["hr_recruiter", "member"],
        max_sensitivity="confidential",
    )

    finance_chunk = {
        "chunk_id": "c3",
        "sensitivity_level": "confidential",
        "allowed_roles": ["finance_analyst", "cfo"],
        "allowed_users": [],
    }

    assert is_chunk_authorized(finance_chunk, finance_ctx) is True
    assert is_chunk_authorized(finance_chunk, hr_ctx) is False


def test_direct_user_acl_override():
    """A user explicitly named in allowed_users is granted access even if role does not match."""
    contractor_ctx = UserSecurityContext(
        user_id="contractor-999",
        roles=["contractor"],
        max_sensitivity="confidential",
    )
    contractor_chunk = {
        "chunk_id": "c4",
        "sensitivity_level": "internal",
        "allowed_roles": ["full_time_employee"],
        "allowed_users": ["contractor-999"],
    }

    assert is_chunk_authorized(contractor_chunk, contractor_ctx) is True


def test_open_chunk_accessible_to_standard_members():
    """Chunks with empty allowed_roles/allowed_users are accessible to anyone meeting sensitivity."""
    member_ctx = UserSecurityContext(
        user_id="member-7",
        roles=["member"],
        max_sensitivity="internal",
    )
    open_chunk = {
        "chunk_id": "c5",
        "sensitivity_level": "internal",
        "allowed_roles": [],
        "allowed_users": [],
    }

    assert is_chunk_authorized(open_chunk, member_ctx) is True
