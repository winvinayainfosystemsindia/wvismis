"""Activity Log service for multi-tenant audit trails"""

import math
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.activity_log import ActivityLog, ActionType
from app.repositories.activity_log_repository import ActivityLogRepository
from app.schemas.activity_log import (
    ActivityLogFilter,
    PaginatedActivityLogsResponse,
    ActivityLogResponse,
)


class ActivityLogService:
    """Service for activity log operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ActivityLogRepository(db)

    async def log_activity(
        self,
        *,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        action_type: ActionType,
        endpoint: str,
        method: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        changes: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> ActivityLog:
        """Create an audit activity log entry"""
        return await self.repository.create_log(
            organization_id=organization_id,
            user_id=user_id,
            action_type=action_type,
            endpoint=endpoint,
            method=method,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
        )

    async def get_user_activities(
        self,
        user_id: int,
        organization_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedActivityLogsResponse:
        """Get paginated activity logs for a specific user"""
        skip = (page - 1) * page_size
        logs, total = await self.repository.get_filtered(
            organization_id=organization_id,
            user_id=user_id,
            skip=skip,
            limit=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedActivityLogsResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[ActivityLogResponse.model_validate(log) for log in logs],
        )

    async def get_filtered_activities(
        self,
        filters: ActivityLogFilter,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedActivityLogsResponse:
        """Get filtered and paginated activity logs"""
        skip = (page - 1) * page_size
        logs, total = await self.repository.get_filtered(
            organization_id=filters.organization_id,
            user_id=filters.user_id,
            action_type=filters.action_type,
            resource_type=filters.resource_type,
            resource_id=filters.resource_id,
            start_date=filters.start_date,
            end_date=filters.end_date,
            method=filters.method,
            status_code=filters.status_code,
            skip=skip,
            limit=page_size,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedActivityLogsResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[ActivityLogResponse.model_validate(log) for log in logs],
        )
