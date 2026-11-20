"""Pydantic schemas for scheduled reminders"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_serializer


class ReminderBase(BaseModel):
    """Base schema for reminder entity"""
    entity_type: str = Field(..., max_length=64, description="Target entity type e.g. project_task")
    entity_id: int = Field(..., description="Target entity ID")
    title: str = Field(..., max_length=255, description="Subject / title of the reminder")
    description: Optional[str] = Field(None, description="Detailed notes or instructions")
    remind_at: datetime = Field(..., description="When the reminder should trigger")
    send_email: bool = Field(True, description="Whether to trigger an email notification")


class ReminderCreate(ReminderBase):
    """Payload to create a new reminder"""
    pass


class ReminderUpdate(BaseModel):
    """Payload to update an existing reminder"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    remind_at: Optional[datetime] = None
    status: Optional[str] = Field(None, description="pending, sent, or dismissed")
    send_email: Optional[bool] = None


class ReminderResponse(BaseModel):
    """Public representation of a reminder"""
    id: int
    public_id: Optional[Union[str, uuid.UUID]] = None
    entity_type: str
    entity_id: int
    title: str
    description: Optional[str] = None
    remind_at: datetime
    status: str
    send_email: bool
    sent_at: Optional[datetime] = None
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("public_id")
    def serialize_public_id(self, v: Any) -> Optional[str]:
        return str(v) if v is not None else None
