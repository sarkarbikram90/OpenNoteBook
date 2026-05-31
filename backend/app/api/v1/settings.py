"""OpenNotebook — Settings CRUD endpoints.

Per-user model registry and preferences.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.v1.schemas.settings import SettingsResponse, SettingsUpdateRequest
from app.core.deps import CurrentUser, DbSession
from app.infrastructure.db.models import UserSettings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "",
    response_model=SettingsResponse,
    summary="Get current user's settings",
)
async def get_settings(current_user: CurrentUser, db: DbSession) -> SettingsResponse:
    """Return the current user's settings.

    If no settings exist yet, creates a row with default values.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        await db.flush()

    return SettingsResponse.model_validate(settings)


@router.patch(
    "",
    response_model=SettingsResponse,
    summary="Update current user's settings",
    status_code=status.HTTP_200_OK,
)
async def update_settings(
    body: SettingsUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> SettingsResponse:
    """Partially update the current user's settings.

    Only fields included in the request body are updated.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        await db.flush()

    # Apply partial updates
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    await db.flush()

    return SettingsResponse.model_validate(settings)
