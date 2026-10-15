"""Push device registration (any signed-in user)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import Field

from app.dependencies import CurrentUser, DbSession
from app.schemas.common import CamelModel
from app.services import notification_service

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


class DeviceIn(CamelModel):
    """An Expo push token for this phone."""

    expo_push_token: str = Field(
        min_length=10, max_length=255, pattern=r"^(ExponentPushToken|ExpoPushToken)\[.+\]$"
    )
    platform: Literal["android", "ios"] = "android"


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def register_device(body: DeviceIn, db: DbSession, user: CurrentUser) -> Response:
    """Save this phone's push token (call after sign-in)."""
    notification_service.register_device(db, user, body.expo_push_token, body.platform)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/remove", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(body: DeviceIn, db: DbSession, user: CurrentUser) -> Response:
    """Stop notifications to this phone (call on sign-out)."""
    notification_service.unregister_device(db, user, body.expo_push_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
