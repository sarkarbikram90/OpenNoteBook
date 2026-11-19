"""OpenNotebook — Workspaces & RBAC Management API endpoints.

Provides multi-tenant workspace management, governance policy settings
(PII redaction, default sensitivity), and role-based member management
(owner, admin, member, viewer).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.audit import record_audit_event
from app.core.deps import CurrentUser, DbSession
from app.infrastructure.db.models import Organization, User, Workspace, WorkspaceMember

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

_VALID_ROLES = {"owner", "admin", "member", "viewer"}
_VALID_SENSITIVITIES = {"public", "internal", "confidential", "restricted"}


# ── Schemas ─────────────────────────────────────────────────────────────────


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    enable_pii_redaction: bool = True
    default_sensitivity: str = Field(default="internal")


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enable_pii_redaction: bool | None = None
    default_sensitivity: str | None = None


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    role: str
    enable_pii_redaction: bool
    default_sensitivity: str
    member_count: int = 1
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: str = Field(default="member")


class WorkspaceMemberUpdateRequest(BaseModel):
    role: str


class WorkspaceMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    created_at: datetime


# ── Helpers ─────────────────────────────────────────────────────────────────


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"ws-{uuid.uuid4().hex[:8]}"


async def _get_member_role(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
) -> str | None:
    result = await db.execute(
        select(WorkspaceMember.role).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _require_admin_or_owner(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
) -> str:
    role = await _get_member_role(workspace_id, user_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required for workspace management",
        )
    return role


async def _get_or_create_default_org(user: CurrentUser, db: DbSession) -> Organization:
    result = await db.execute(select(Organization).order_by(Organization.created_at.asc()).limit(1))
    org = result.scalar_one_or_none()
    if org is not None:
        return org

    org = Organization(
        name="OpenNotebook Organization",
        slug=f"org-{str(user.id)[:8]}",
    )
    db.add(org)
    await db.flush()
    return org


async def _ensure_personal_workspace(user: CurrentUser, db: DbSession) -> tuple[Workspace, str]:
    """Ensure the authenticated user belongs to at least one workspace."""
    org = await _get_or_create_default_org(user, db)
    workspace = Workspace(
        organization_id=org.id,
        name="Personal Workspace",
        slug=f"personal-{str(user.id)[:8]}",
        enable_pii_redaction=True,
        default_sensitivity="internal",
    )
    db.add(workspace)
    await db.flush()

    membership = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
    )
    db.add(membership)
    await db.flush()
    return workspace, "owner"


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="List workspaces for the current user",
)
async def list_workspaces(
    user: CurrentUser,
    db: DbSession,
) -> list[WorkspaceResponse]:
    """Return all workspaces the current user belongs to, auto-bootstrapping one if empty."""
    rows_result = await db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(Workspace.created_at.asc())
    )
    rows: list[tuple[Workspace, str]] = [
        (ws, role) for ws, role in rows_result.all()
    ]

    if not rows:
        ws, role = await _ensure_personal_workspace(user, db)
        rows = [(ws, role)]

    responses: list[WorkspaceResponse] = []
    for ws, role in rows:
        count_res = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == ws.id
            )
        )
        member_count = int(count_res.scalar() or 1)
        responses.append(
            WorkspaceResponse(
                id=ws.id,
                organization_id=ws.organization_id,
                name=ws.name,
                slug=ws.slug,
                role=role,
                enable_pii_redaction=ws.enable_pii_redaction,
                default_sensitivity=ws.default_sensitivity,
                member_count=member_count,
                created_at=ws.created_at,
                updated_at=ws.updated_at,
            )
        )
    return responses


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    payload: WorkspaceCreateRequest,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceResponse:
    """Create a collaborative workspace and assign the creator as owner."""
    sensitivity = payload.default_sensitivity.lower().strip()
    if sensitivity not in _VALID_SENSITIVITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sensitivity level. Expected one of: {sorted(_VALID_SENSITIVITIES)}",
        )

    org = await _get_or_create_default_org(user, db)
    ws = Workspace(
        organization_id=org.id,
        name=payload.name.strip(),
        slug=f"{_slugify(payload.name)}-{uuid.uuid4().hex[:6]}",
        enable_pii_redaction=payload.enable_pii_redaction,
        default_sensitivity=sensitivity,
    )
    db.add(ws)
    await db.flush()

    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    await db.flush()

    await record_audit_event(
        db=db,
        action="workspace.create",
        resource_type="workspace",
        resource_id=str(ws.id),
        user_id=user.id,
        details={"name": ws.name, "default_sensitivity": ws.default_sensitivity},
    )

    return WorkspaceResponse(
        id=ws.id,
        organization_id=ws.organization_id,
        name=ws.name,
        slug=ws.slug,
        role="owner",
        enable_pii_redaction=ws.enable_pii_redaction,
        default_sensitivity=ws.default_sensitivity,
        member_count=1,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace settings and governance policy",
)
async def update_workspace(
    workspace_id: uuid.UUID,
    payload: WorkspaceUpdateRequest,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceResponse:
    """Update workspace name, PII redaction toggle, or default sensitivity level."""
    role = await _require_admin_or_owner(workspace_id, user.id, db)

    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = result.scalar_one_or_none()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if payload.name is not None:
        ws.name = payload.name.strip()
    if payload.enable_pii_redaction is not None:
        ws.enable_pii_redaction = payload.enable_pii_redaction
    if payload.default_sensitivity is not None:
        sensitivity = payload.default_sensitivity.lower().strip()
        if sensitivity not in _VALID_SENSITIVITIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sensitivity level. Expected one of: {sorted(_VALID_SENSITIVITIES)}",
            )
        ws.default_sensitivity = sensitivity

    await db.flush()

    count_res = await db.execute(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == ws.id
        )
    )
    member_count = int(count_res.scalar() or 1)

    await record_audit_event(
        db=db,
        action="workspace.update",
        resource_type="workspace",
        resource_id=str(ws.id),
        user_id=user.id,
        details={
            "enable_pii_redaction": ws.enable_pii_redaction,
            "default_sensitivity": ws.default_sensitivity,
        },
    )

    return WorkspaceResponse(
        id=ws.id,
        organization_id=ws.organization_id,
        name=ws.name,
        slug=ws.slug,
        role=role,
        enable_pii_redaction=ws.enable_pii_redaction,
        default_sensitivity=ws.default_sensitivity,
        member_count=member_count,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    summary="List members of a workspace",
)
async def list_workspace_members(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[WorkspaceMemberResponse]:
    """List workspace members and their RBAC roles."""
    role = await _get_member_role(workspace_id, user.id, db)
    if role is None:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")

    result = await db.execute(
        select(WorkspaceMember, User.email)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    return [
        WorkspaceMemberResponse(
            user_id=member.user_id,
            email=email,
            role=member.role,
            created_at=member.created_at,
        )
        for member, email in result.all()
    ]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a user to a workspace by email",
)
async def add_workspace_member(
    workspace_id: uuid.UUID,
    payload: WorkspaceMemberCreateRequest,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceMemberResponse:
    """Invite/add an existing registered user to a workspace with an RBAC role."""
    await _require_admin_or_owner(workspace_id, user.id, db)

    role = payload.role.lower().strip()
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Expected one of: {sorted(_VALID_ROLES)}",
        )

    user_res = await db.execute(
        select(User).where(func.lower(User.email) == payload.email.strip().lower())
    )
    target_user = user_res.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered user found with email '{payload.email}'",
        )

    existing_res = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user.id,
        )
    )
    if existing_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this workspace",
        )

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=target_user.id,
        role=role,
    )
    db.add(member)
    await db.flush()

    await record_audit_event(
        db=db,
        action="workspace.member_add",
        resource_type="workspace",
        resource_id=str(workspace_id),
        user_id=user.id,
        details={"target_user_id": str(target_user.id), "email": target_user.email, "role": role},
    )

    return WorkspaceMemberResponse(
        user_id=target_user.id,
        email=target_user.email,
        role=member.role,
        created_at=member.created_at,
    )


@router.patch(
    "/{workspace_id}/members/{member_user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Update a workspace member's RBAC role",
)
async def update_workspace_member_role(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    payload: WorkspaceMemberUpdateRequest,
    user: CurrentUser,
    db: DbSession,
) -> WorkspaceMemberResponse:
    """Change a member's RBAC role while ensuring at least one owner remains."""
    await _require_admin_or_owner(workspace_id, user.id, db)

    new_role = payload.role.lower().strip()
    if new_role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Expected one of: {sorted(_VALID_ROLES)}",
        )

    result = await db.execute(
        select(WorkspaceMember, User.email)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    member, email = row

    if member.role == "owner" and new_role != "owner":
        owners_count = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "owner",
            )
        )
        if int(owners_count.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last workspace owner",
            )

    member.role = new_role
    await db.flush()

    await record_audit_event(
        db=db,
        action="workspace.member_role_update",
        resource_type="workspace",
        resource_id=str(workspace_id),
        user_id=user.id,
        details={"target_user_id": str(member_user_id), "role": new_role},
    )

    return WorkspaceMemberResponse(
        user_id=member.user_id,
        email=email,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete(
    "/{workspace_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a workspace",
)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Remove a member from the workspace (cannot remove the last owner)."""
    await _require_admin_or_owner(workspace_id, user.id, db)

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Workspace member not found")

    if member.role == "owner":
        owners_count = await db.execute(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "owner",
            )
        )
        if int(owners_count.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last workspace owner",
            )

    await db.delete(member)
    await db.flush()

    await record_audit_event(
        db=db,
        action="workspace.member_remove",
        resource_type="workspace",
        resource_id=str(workspace_id),
        user_id=user.id,
        details={"target_user_id": str(member_user_id)},
    )
