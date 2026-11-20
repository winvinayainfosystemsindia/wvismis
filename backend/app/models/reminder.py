"""Reminder model for Project Tasks, Leads, and general entity reminders"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User


class Reminder(BaseModel, TenantMixin):
    """Database model for in-app and email scheduled reminders"""

    __tablename__ = "reminders"

    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        unique=True,
        index=True,
        nullable=False,
        default=uuid.uuid4,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Entity type e.g. 'project_task', 'lead', 'project'",
    )
    entity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        doc="Foreign primary key of the target entity",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Title or subject of the reminder",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Optional note or context for the reminder",
    )
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        doc="Timestamp when the reminder should trigger",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
        doc="Status: 'pending', 'sent', 'dismissed'",
    )
    send_email: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether to send an email notification when due",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when the reminder was sent/processed",
    )

    user: Mapped["User"] = relationship("User", lazy="joined")
