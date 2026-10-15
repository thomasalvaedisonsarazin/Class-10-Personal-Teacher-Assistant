"""Push device tokens and notification log (Phase 2B)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin


class DeviceToken(TimestampMixin, Base):
    """An Expo push token registered by a user's device."""

    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expo_push_token: Mapped[str] = mapped_column(
        sa.String(255), unique=True, index=True, nullable=False
    )
    platform: Mapped[str] = mapped_column(sa.String(16), nullable=False)


class NotificationLog(TimestampMixin, Base):
    """A record of a notification sent to a user."""

    __tablename__ = "notification_logs"
    __table_args__ = (sa.Index("ix_notification_logs_user_sent", "user_id", "sent_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
