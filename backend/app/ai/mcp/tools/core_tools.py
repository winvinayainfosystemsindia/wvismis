"""
Harness Agentic AI Tools — Multi-Tenancy, Users, Audit & Real-Time Streaming Tools
==================================================================================

Registered tools available to the AI Harness for inspecting and managing
the current Organization, Users, Activity Logs, and WebSocket streams.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING
from sqlalchemy import select, func
from app.ai.brain.schemas import ToolDefinition, ToolParameterSchema, ToolResult
from app.ai.mcp.base_tool import BaseTool
from app.ai.mcp.registry import registry
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.activity_log import ActivityLog
from app.core.websocket import ws_manager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GetOrganizationOverviewTool(BaseTool):
    """Returns summary and quota utilization for the user's current Organization."""

    definition = ToolDefinition(
        name="get_organization_overview",
        description="Get multi-tenant organization profile, subscription plan, user quota, and active user statistics.",
        category="organization",
        is_read_only=True,
        requires_approval=False,
        parameters={},
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        if not user.organization_id:
            return ToolResult(
                success=False,
                message="Current user is not assigned to an organization.",
            )

        org_res = await db.execute(
            select(Organization).where(Organization.id == user.organization_id)
        )
        org = org_res.scalar_one_or_none()
        if not org:
            return ToolResult(success=False, message="Organization record not found.")

        total_users_res = await db.execute(
            select(func.count(User.id)).where(
                User.organization_id == org.id,
                User.is_deleted == False,
            )
        )
        total_users = total_users_res.scalar() or 0

        active_users_res = await db.execute(
            select(func.count(User.id)).where(
                User.organization_id == org.id,
                User.is_deleted == False,
                User.is_active == True,
            )
        )
        active_users = active_users_res.scalar() or 0

        data = {
            "organization_id": org.id,
            "name": org.name,
            "slug": org.slug,
            "domain": org.domain,
            "subscription_plan": org.subscription_plan.value,
            "is_active": org.is_active,
            "max_users": org.max_users,
            "total_users": total_users,
            "active_users": active_users,
            "remaining_seats": max(0, org.max_users - active_users),
        }
        return ToolResult(
            success=True,
            message=(
                f"Organization **{org.name}** (`{org.slug}`) is on the **{org.subscription_plan.value}** plan "
                f"with **{active_users}/{org.max_users}** active users."
            ),
            data=data,
        )


class SearchOrganizationUsersTool(BaseTool):
    """Searches or lists users within the current user's Organization."""

    definition = ToolDefinition(
        name="search_organization_users",
        description="Search or list users in the current organization by keyword or role.",
        category="users",
        is_read_only=True,
        requires_approval=False,
        parameters={
            "query": ToolParameterSchema(
                type="string",
                description="Optional search term for name, email, username, or department",
            ),
            "role": ToolParameterSchema(
                type="string",
                description="Optional role filter",
                enum=[r.value for r in UserRole],
            ),
            "limit": ToolParameterSchema(
                type="integer",
                description="Max number of users to return (default 10)",
                default=10,
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        query_str = params.get("query")
        role_str = params.get("role")
        limit = min(int(params.get("limit", 10)), 50)

        stmt = select(User).where(
            User.organization_id == user.organization_id,
            User.is_deleted == False,
        )
        if role_str:
            stmt = stmt.where(User.role == role_str)
        if query_str:
            stmt = stmt.where(
                User.full_name.ilike(f"%{query_str}%")
                | User.email.ilike(f"%{query_str}%")
                | User.username.ilike(f"%{query_str}%")
                | User.department.ilike(f"%{query_str}%")
            )

        res = await db.execute(stmt.order_by(User.id.desc()).limit(limit))
        users = list(res.scalars().all())

        user_list = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value,
                "department": u.department,
                "is_active": u.is_active,
            }
            for u in users
        ]
        return ToolResult(
            success=True,
            message=f"Found **{len(user_list)}** user(s) in your organization matching the criteria.",
            data={"users": user_list, "count": len(user_list)},
        )


class GetUserRoleBreakdownTool(BaseTool):
    """Returns count of users grouped by role within the organization."""

    definition = ToolDefinition(
        name="get_user_role_breakdown",
        description="Get a statistical breakdown of users by role and active status in the current organization.",
        category="users",
        is_read_only=True,
        requires_approval=False,
        parameters={},
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        role_query = (
            select(User.role, func.count(User.id))
            .where(
                User.organization_id == user.organization_id,
                User.is_deleted == False,
            )
            .group_by(User.role)
        )
        role_res = await db.execute(role_query)
        by_role = {role.value: count for role, count in role_res.all()}
        total = sum(by_role.values())

        breakdown_str = ", ".join(f"**{r}**: {c}" for r, c in by_role.items()) or "No users"
        return ToolResult(
            success=True,
            message=f"Total users in organization: **{total}** ({breakdown_str}).",
            data={"total": total, "by_role": by_role},
        )


class GetRecentAuditLogsTool(BaseTool):
    """Fetches recent audit activity logs for the current organization."""

    definition = ToolDefinition(
        name="get_recent_audit_logs",
        description="Fetch the most recent audit activity logs in the current organization.",
        category="audit",
        is_read_only=True,
        requires_approval=False,
        parameters={
            "limit": ToolParameterSchema(
                type="integer",
                description="Number of recent activity logs to retrieve (default 10)",
                default=10,
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        limit = min(int(params.get("limit", 10)), 50)
        stmt = (
            select(ActivityLog)
            .where(
                ActivityLog.organization_id == user.organization_id,
                ActivityLog.is_deleted == False,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        logs = list(res.scalars().all())

        items = [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action_type": log.action_type.value,
                "endpoint": log.endpoint,
                "method": log.method,
                "resource_type": log.resource_type,
                "status_code": log.status_code,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
        return ToolResult(
            success=True,
            message=f"Retrieved **{len(items)}** recent audit activity log entries.",
            data={"logs": items},
        )


class BroadcastOrganizationAlertTool(BaseTool):
    """Broadcasts a real-time WebSocket notification to all connected users in the organization."""

    definition = ToolDefinition(
        name="broadcast_organization_alert",
        description="Broadcast a real-time notification event over WebSockets to all active users in the organization.",
        category="streaming",
        is_read_only=False,
        requires_approval=False,
        parameters={
            "title": ToolParameterSchema(
                type="string",
                description="Alert title",
            ),
            "message": ToolParameterSchema(
                type="string",
                description="Alert message body",
            ),
            "channel": ToolParameterSchema(
                type="string",
                description="Target WebSocket channel (default: 'notifications')",
                default="notifications",
            ),
        },
        required_parameters=["title", "message"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        if not user.organization_id:
            return ToolResult(success=False, message="User is not associated with an organization.")

        title = params["title"]
        message = params["message"]
        channel = params.get("channel") or "notifications"

        delivered = await ws_manager.broadcast_to_organization(
            organization_id=user.organization_id,
            event_type="ai.organization.alert",
            channel=channel,
            data={
                "title": title,
                "message": message,
                "sender_user_id": user.id,
                "sender_name": user.full_name or user.username,
            },
        )
        return ToolResult(
            success=True,
            message=f"Broadcasted alert **'{title}'** on channel `{channel}` to **{delivered}** active WebSocket connection(s).",
            data={"delivered_connections": delivered, "channel": channel},
        )


class DeactivateOrganizationUserTool(BaseTool):
    """Deactivates a user account in the organization — protected by Human-in-the-Loop approval gate."""

    definition = ToolDefinition(
        name="deactivate_organization_user",
        description="Deactivate a user account in the organization. Requires human approval before execution.",
        category="users",
        is_read_only=False,
        requires_approval=True,
        parameters={
            "target_user_id": ToolParameterSchema(
                type="integer",
                description="ID of the user to deactivate",
            ),
            "reason": ToolParameterSchema(
                type="string",
                description="Audit reason for deactivating the user",
            ),
        },
        required_parameters=["target_user_id", "reason"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        target_id = int(params["target_user_id"])
        if target_id == user.id:
            return ToolResult(success=False, message="Cannot deactivate your own account.")

        res = await db.execute(
            select(User).where(
                User.id == target_id,
                User.organization_id == user.organization_id,
                User.is_deleted == False,
            )
        )
        target_user = res.scalar_one_or_none()
        if not target_user:
            return ToolResult(success=False, message=f"User ID {target_id} not found in your organization.")

        target_user.is_active = False
        await db.flush()
        return ToolResult(
            success=True,
            message=f"User **{target_user.email}** (ID: {target_user.id}) has been deactivated.",
            data={"user_id": target_user.id, "is_active": False},
            records_affected=1,
        )


def register_core_tools() -> None:
    """Register all built-in WVISMIS Harness tools."""
    registry.register(GetOrganizationOverviewTool())
    registry.register(SearchOrganizationUsersTool())
    registry.register(GetUserRoleBreakdownTool())
    registry.register(GetRecentAuditLogsTool())
    registry.register(BroadcastOrganizationAlertTool())
    registry.register(DeactivateOrganizationUserTool())


register_core_tools()
