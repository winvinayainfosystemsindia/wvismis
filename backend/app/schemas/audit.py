"""Pydantic validation schemas for Audit Logs"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by_user_id: Optional[int] = None
    changed_at: datetime
