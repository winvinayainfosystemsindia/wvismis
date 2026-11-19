"""Activity Log Pydantic schemas for validation"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.models.activity_log import ActionType


class ActivityLogBase(BaseModel):
    """Base activity log schema"""
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    action_type: ActionType
    endpoint: str
    method: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    changes: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status_code: Optional[int] = None


class ActivityLogCreate(ActivityLogBase):
    """Schema for creating an activity log entry"""
    pass


class ActivityLogResponse(ActivityLogBase):
    """Schema for activity log response"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityLogFilter(BaseModel):
    """Schema for filtering activity logs"""
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    action_type: Optional[ActionType] = None
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    method: Optional[str] = None
    status_code: Optional[int] = None


class PaginatedActivityLogsResponse(BaseModel):
    """Paginated activity logs response"""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[ActivityLogResponse]
