"""OpenNotebook — Query-time access resolution.

Turns an authenticated user into a :class:`UserSecurityContext` used by the
retrieval pipeline to trim chunks the user is not authorized to see.

Design:
- A user's roles for a notebook come from ownership (implicit ``owner``) plus
  their workspace membership role (``WorkspaceMember.role``).
- Roles map to a maximum data-``sensitivity`` clearance.

In a future IdP integration, group claims can be added to ``roles`` here
without changing the retrieval pipeline.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.domain.retrieval.retriever import UserSecurityContext

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.db.models import Notebook

logger = logging.getLogger(__name__)

# Role -> maximum sensitivity clearance.
ROLE_CLEARANCE: dict[str, str] = {
    "viewer": "internal",
    "member": "confidential",
    "admin": "restricted",
    "owner": "restricted",
}

_CLEARANCE_RANK = {"public": 1, "internal": 2, "confidential": 3, "restricted": 4}
_DEFAULT_CLEARANCE = "internal"


def clearance_for_roles(roles: list[str]) -> str:
    """Return the highest sensitivity clearance granted by a set of roles."""
    best = _DEFAULT_CLEARANCE
    for role in roles:
        clearance = ROLE_CLEARANCE.get(role.lower())
        if clearance and _CLEARANCE_RANK[clearance] > _CLEARANCE_RANK[best]:
            best = clearance
    return best


def build_security_context(
    user_id: str,
    roles: list[str],
    workspace_id: str | None = None,
) -> UserSecurityContext:
    """Construct the retrieval security context for a user."""
    effective_roles = roles or ["viewer"]
    return UserSecurityContext(
        user_id=str(user_id),
        workspace_id=str(workspace_id) if workspace_id else None,
        roles=list(effective_roles),
        max_sensitivity=clearance_for_roles(effective_roles),
    )


async def resolve_notebook_roles(
    db: AsyncSession,
    notebook: Notebook,
    user_id: uuid.UUID,
) -> list[str]:
    """Return the roles a user holds for a notebook (owner and/or workspace role)."""
    roles: list[str] = []
    if str(notebook.user_id) == str(user_id):
        roles.append("owner")

    if notebook.workspace_id is not None:
        from app.infrastructure.db.models import WorkspaceMember

        result = await db.execute(
            select(WorkspaceMember.role).where(
                WorkspaceMember.workspace_id == notebook.workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        workspace_role = result.scalar_one_or_none()
        if workspace_role is not None:
            roles.append(workspace_role)

    return roles


async def authorize_notebook_access(
    db: AsyncSession,
    notebook_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[Notebook, UserSecurityContext] | None:
    """Resolve a user's access to a notebook.

    Returns:
        ``(notebook, security_context)`` when the user may access the notebook
        (owner or workspace member), otherwise ``None``.
    """
    from app.infrastructure.db.models import Notebook

    result = await db.execute(select(Notebook).where(Notebook.id == notebook_id))
    notebook = result.scalar_one_or_none()
    if notebook is None:
        return None

    roles = await resolve_notebook_roles(db, notebook, user_id)
    if not roles:
        return None

    return notebook, build_security_context(str(user_id), roles, notebook.workspace_id)
