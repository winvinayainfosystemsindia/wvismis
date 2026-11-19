"""WebSocket real-time streaming schemas"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WSBroadcastRequest(BaseModel):
    """Request payload to broadcast a real-time event over WebSockets"""
    event_type: str = Field(..., description="Event identifier, e.g. 'data.updated', 'notification.alert'")
    channel: str = Field("general", description="Target topic channel within the organization")
    data: Dict[str, Any] = Field(default_factory=dict, description="JSON payload to stream")
    target_user_id: Optional[int] = Field(
        None,
        description="Optional: send only to a specific user ID in the organization",
    )


class WSBroadcastResponse(BaseModel):
    """Response from broadcasting a real-time event"""
    delivered_connections: int
    organization_id: int
    channel: str
    event_type: str


class WSStatsResponse(BaseModel):
    """Active WebSocket connection statistics for an organization"""
    organization_id: int
    active_connections: int
    active_unique_users: int
    active_user_ids: List[int]
    channels: Dict[str, int]
