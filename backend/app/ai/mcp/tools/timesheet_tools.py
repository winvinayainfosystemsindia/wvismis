"""
Harness Agentic AI Tools — Timesheet & Attendance Module
========================================================

Registered MCP tools enabling ARIA to inspect, log, submit, audit, and approve
daily and weekly employee timesheets, enforce reporting manager allocation,
and evaluate organization timesheet compliance.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any, TYPE_CHECKING
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.ai.brain.schemas import ToolDefinition, ToolParameterSchema, ToolResult
from app.ai.mcp.base_tool import BaseTool
from app.ai.mcp.registry import registry
from app.models.user import User, UserRole
from app.models.project import Project, ProjectTask
from app.models.timesheet import (
    ProjectTimeLog,
    TimesheetStatus,
    TimesheetBillingType,
    TimesheetWeekUnlockRequest,
    WeekUnlockStatus,
    UnlockRequestType,
    UserTimesheetCategory,
    TimesheetUserSettings,
)
from app.services.timesheet import (
    get_week_bounds,
    is_within_free_edit_window,
    can_manage_timesheet_for,
    is_admin_user,
    TimesheetService,
)
from app.repositories.timesheet import (
    ProjectTimeLogRepository,
    TimesheetWeekUnlockRequestRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GetMyTimesheetSummaryTool(BaseTool):
    """Retrieves the current user's weekly timesheet progress, target hours, and missing days."""

    definition = ToolDefinition(
        name="get_my_timesheet_summary",
        description="Get your logged hours summary for the current or previous week, including target completion, daily breakdown, and missing days.",
        category="timesheet",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "period": ToolParameterSchema(
                type="string",
                description="Target period: 'current_week', 'previous_week', or date in YYYY-MM-DD format",
                default="current_week",
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        period = (params.get("period") or "current_week").strip().lower()
        today = date.today()

        if period == "previous_week":
            target_date = today - timedelta(days=7)
        elif period == "current_week":
            target_date = today
        else:
            try:
                target_date = date.fromisoformat(period)
            except ValueError:
                target_date = today

        week_start, week_end = get_week_bounds(target_date)

        # Retrieve user target hours (default 40.0h)
        settings_res = await db.execute(
            select(TimesheetUserSettings).where(
                TimesheetUserSettings.user_id == user.id,
                TimesheetUserSettings.organization_id == user.organization_id,
            )
        )
        user_settings = settings_res.scalar_one_or_none()
        weekly_target = float(user_settings.weekly_hours_target) if user_settings and user_settings.weekly_hours_target else 40.0

        # Query all logs for this week
        logs_res = await db.execute(
            select(ProjectTimeLog)
            .options(
                selectinload(ProjectTimeLog.project),
                selectinload(ProjectTimeLog.task),
                selectinload(ProjectTimeLog.category),
            )
            .where(
                ProjectTimeLog.user_id == user.id,
                ProjectTimeLog.organization_id == user.organization_id,
                ProjectTimeLog.log_date >= week_start,
                ProjectTimeLog.log_date <= week_end,
                ProjectTimeLog.is_deleted == False,
            )
            .order_by(ProjectTimeLog.log_date.asc())
        )
        logs = list(logs_res.scalars().all())

        total_hours = sum(float(l.hours) for l in logs)
        billable_hours = sum(float(l.hours) for l in logs if l.billing_type == TimesheetBillingType.BILLABLE)
        non_billable_hours = total_hours - billable_hours

        # Day-by-day mapping
        days_map: dict[str, dict[str, Any]] = {}
        cur = week_start
        while cur <= week_end:
            d_str = cur.isoformat()
            day_name = cur.strftime("%A")
            day_logs = [l for l in logs if l.log_date == cur]
            day_total = sum(float(l.hours) for l in day_logs)
            day_status = "Approved" if any(l.status == TimesheetStatus.APPROVED for l in day_logs) else \
                         "Submitted" if any(l.status == TimesheetStatus.SUBMITTED for l in day_logs) else \
                         "Draft" if day_logs else "Empty"

            days_map[d_str] = {
                "day_name": day_name,
                "hours": round(day_total, 2),
                "status": day_status,
                "entries_count": len(day_logs),
            }
            cur += timedelta(days=1)

        # Check missing work days (Monday - Friday)
        missing_work_days = []
        cur = week_start
        while cur <= min(week_end, today):
            if cur.weekday() < 5 and days_map[cur.isoformat()]["hours"] == 0:
                missing_work_days.append(f"{cur.strftime('%A')} ({cur.isoformat()})")
            cur += timedelta(days=1)

        has_approved = any(l.status == TimesheetStatus.APPROVED for l in logs)
        has_submitted = any(l.status == TimesheetStatus.SUBMITTED for l in logs)
        overall_status = "Approved" if has_approved else "Submitted" if has_submitted else "Draft" if logs else "No Entries"

        # Reporting manager check
        mgr_name = "Not Assigned"
        if user.reporting_manager_id:
            mgr_res = await db.execute(select(User).where(User.id == user.reporting_manager_id))
            mgr = mgr_res.scalar_one_or_none()
            if mgr:
                mgr_name = mgr.full_name or mgr.username

        data = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_hours": round(total_hours, 2),
            "weekly_target_hours": weekly_target,
            "target_completion_pct": round((total_hours / weekly_target * 100), 1) if weekly_target > 0 else 0.0,
            "billable_hours": round(billable_hours, 2),
            "non_billable_hours": round(non_billable_hours, 2),
            "overall_week_status": overall_status,
            "reporting_manager": mgr_name,
            "daily_breakdown": days_map,
            "missing_work_days": missing_work_days,
        }

        missing_alert = f"\n⚠️ **Missing Time**: No hours logged for: {', '.join(missing_work_days)}." if missing_work_days else "\n✅ All workdays up to today have logged hours."

        msg = (
            f"### Timesheet Summary ({week_start.isoformat()} to {week_end.isoformat()})\n"
            f"- **Total Logged**: **{data['total_hours']}h** / {weekly_target}h ({data['target_completion_pct']}% of weekly target)\n"
            f"- **Status**: `{overall_status}` | **Reporting Manager**: {mgr_name}\n"
            f"- **Billable / Non-Billable**: {data['billable_hours']}h / {data['non_billable_hours']}h"
            f"{missing_alert}"
        )

        return ToolResult(success=True, message=msg, data=data)


class LogWorkTimeTool(BaseTool):
    """Logs work hours against a project, task, or internal category."""

    definition = ToolDefinition(
        name="log_work_time",
        description="Log daily hours worked on a project, task, or category with notes, auto-resolving names to IDs.",
        category="timesheet",
        is_read_only=False,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "log_date": ToolParameterSchema(
                type="string",
                description="Date of work in YYYY-MM-DD format (default: today)",
            ),
            "hours": ToolParameterSchema(
                type="number",
                description="Number of hours to log (e.g. 4, 7.5)",
            ),
            "project_name": ToolParameterSchema(
                type="string",
                description="Name or partial name of the project",
            ),
            "project_id": ToolParameterSchema(
                type="integer",
                description="Project database ID (if known)",
            ),
            "task_id": ToolParameterSchema(
                type="integer",
                description="Optional project task ID",
            ),
            "category_name": ToolParameterSchema(
                type="string",
                description="Internal category (e.g. Meeting, Support, Training, Leave) if not logging to a project",
            ),
            "notes": ToolParameterSchema(
                type="string",
                description="Brief description of activities completed",
            ),
            "billing_type": ToolParameterSchema(
                type="string",
                description="Billing classification: 'billable' or 'non_billable'",
                enum=[b.value for b in TimesheetBillingType],
                default="billable",
            ),
            "submit": ToolParameterSchema(
                type="boolean",
                description="Whether to submit this entry immediately for daily approval",
                default=False,
            ),
        },
        required_parameters=["hours"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        hours = float(params["hours"])
        if hours <= 0 or hours > 24:
            return ToolResult(success=False, message="Hours must be greater than 0 and at most 24 per day.")

        # Resolve date
        log_date = date.today()
        if params.get("log_date"):
            try:
                log_date = date.fromisoformat(params["log_date"])
            except ValueError:
                return ToolResult(success=False, message="Invalid date format. Please use YYYY-MM-DD.")

        # Check free edit window (today, previous day, current week, and previous week)
        if not is_within_free_edit_window(log_date):
            return ToolResult(
                success=False,
                message=f"Date {log_date.isoformat()} is outside the permitted modification window (current week and previous week). An approved Revoke or Unlock Request is required.",
            )

        project_id = params.get("project_id")
        project_name = params.get("project_name")
        task_id = params.get("task_id")
        category_name = params.get("category_name")
        notes = params.get("notes") or ""
        billing_type_val = params.get("billing_type") or "billable"
        submit_flag = bool(params.get("submit", False))

        # Auto-resolve project by name if given
        resolved_project: Project | None = None
        if not project_id and project_name:
            p_res = await db.execute(
                select(Project).where(
                    Project.organization_id == user.organization_id,
                    Project.name.ilike(f"%{project_name.strip()}%"),
                    Project.is_deleted == False,
                )
            )
            resolved_project = p_res.scalars().first()
            if resolved_project:
                project_id = resolved_project.id
            else:
                return ToolResult(success=False, message=f"No project matching '{project_name}' found in your organization.")
        elif project_id:
            p_res = await db.execute(
                select(Project).where(
                    Project.id == int(project_id),
                    Project.organization_id == user.organization_id,
                    Project.is_deleted == False,
                )
            )
            resolved_project = p_res.scalar_one_or_none()
            if not resolved_project:
                return ToolResult(success=False, message=f"Project ID {project_id} not found in your organization.")

        # Auto-resolve category if given
        category_id = None
        if category_name and not project_id:
            cat_res = await db.execute(
                select(UserTimesheetCategory).where(
                    UserTimesheetCategory.organization_id == user.organization_id,
                    UserTimesheetCategory.name.ilike(f"%{category_name.strip()}%"),
                    UserTimesheetCategory.is_deleted == False,
                )
            )
            cat = cat_res.scalars().first()
            if cat:
                category_id = cat.id
            else:
                # Fallback to org default or create category
                category_id = None

        if not project_id and not category_id:
            # If neither project nor category specified, find default General category
            cat_res = await db.execute(
                select(UserTimesheetCategory).where(
                    UserTimesheetCategory.organization_id == user.organization_id,
                    UserTimesheetCategory.is_deleted == False,
                ).limit(1)
            )
            default_cat = cat_res.scalar_one_or_none()
            if default_cat:
                category_id = default_cat.id
            else:
                return ToolResult(success=False, message="Please specify a project or category for this time entry.")

        # Check daily cap
        day_total = await ProjectTimeLogRepository.get_day_total_hours(
            db, user.organization_id, user.id, log_date
        )
        if day_total + hours > 24.0:
            return ToolResult(
                success=False,
                message=f"Logging {hours}h on {log_date.isoformat()} exceeds the daily limit of 24h (already logged {day_total}h).",
            )

        # Check manager assignment if submit requested
        if submit_flag and not user.reporting_manager_id:
            return ToolResult(
                success=False,
                message="Cannot submit timesheet: You do not have an allocated Reporting Manager. Please request an admin or manager to assign your reporting manager first.",
            )

        status_val = TimesheetStatus.SUBMITTED if submit_flag else TimesheetStatus.DRAFT

        log = await ProjectTimeLogRepository.create(
            db,
            organization_id=user.organization_id,
            user_id=user.id,
            project_id=project_id,
            task_id=int(task_id) if task_id else None,
            category_id=category_id,
            log_date=log_date,
            hours=hours,
            notes=notes,
            billing_type=TimesheetBillingType(billing_type_val),
            status=status_val,
        )
        await db.commit()

        target_name = resolved_project.name if resolved_project else category_name or "General"
        msg = (
            f"Successfully logged **{hours} hours** on **{target_name}** for **{log_date.isoformat()}** "
            f"(`{billing_type_val}`, Status: `{status_val.value}`)."
        )
        return ToolResult(
            success=True,
            message=msg,
            data={"log_id": log.id, "hours": hours, "log_date": log_date.isoformat(), "status": status_val.value},
            records_affected=1,
        )


class SubmitTimesheetTool(BaseTool):
    """Submits daily or weekly timesheets to the allocated reporting manager."""

    definition = ToolDefinition(
        name="submit_timesheet",
        description="Submit timesheet entries for daily or weekly review by your allocated reporting manager.",
        category="timesheet",
        is_read_only=False,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "submission_type": ToolParameterSchema(
                type="string",
                description="'daily' for today/specific date, or 'weekly' for the full week",
                enum=["daily", "weekly"],
                default="weekly",
            ),
            "target_date": ToolParameterSchema(
                type="string",
                description="Target date in YYYY-MM-DD format (default: today)",
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        sub_type = (params.get("submission_type") or "weekly").strip().lower()
        target_date = date.today()
        if params.get("target_date"):
            try:
                target_date = date.fromisoformat(params["target_date"])
            except ValueError:
                pass

        if not user.reporting_manager_id:
            return ToolResult(
                success=False,
                message="Submission blocked: You do not have an assigned Reporting Manager. Please contact your administrator to assign your reporting manager in the Timesheet module.",
            )

        if sub_type == "daily":
            logs = await ProjectTimeLogRepository.get_draft_logs_for_day(
                db, user.organization_id, user.id, target_date
            )
            if not logs:
                return ToolResult(
                    success=True,
                    message=f"No draft time entries found to submit for {target_date.isoformat()}.",
                    data={"submitted_count": 0},
                )
            for l in logs:
                l.status = TimesheetStatus.SUBMITTED
            await db.commit()
            return ToolResult(
                success=True,
                message=f"Successfully submitted **{len(logs)}** time entry/entries for **{target_date.isoformat()}** to your reporting manager.",
                data={"submitted_count": len(logs), "date": target_date.isoformat()},
                records_affected=len(logs),
            )
        else:
            week_start, week_end = get_week_bounds(target_date)
            # Find all draft entries for the week
            drafts_res = await db.execute(
                select(ProjectTimeLog).where(
                    ProjectTimeLog.user_id == user.id,
                    ProjectTimeLog.organization_id == user.organization_id,
                    ProjectTimeLog.log_date >= week_start,
                    ProjectTimeLog.log_date <= week_end,
                    ProjectTimeLog.status == TimesheetStatus.DRAFT,
                    ProjectTimeLog.is_deleted == False,
                )
            )
            drafts = list(drafts_res.scalars().all())
            if not drafts:
                return ToolResult(
                    success=True,
                    message=f"No draft entries to submit for the week of {week_start.isoformat()} to {week_end.isoformat()}.",
                    data={"submitted_count": 0},
                )

            for l in drafts:
                l.status = TimesheetStatus.SUBMITTED
            await db.commit()

            return ToolResult(
                success=True,
                message=f"Successfully submitted **{len(drafts)}** entries for the week of **{week_start.isoformat()} to {week_end.isoformat()}** to your reporting manager for weekly approval.",
                data={"submitted_count": len(drafts), "week_start": week_start.isoformat(), "week_end": week_end.isoformat()},
                records_affected=len(drafts),
            )


class GetPendingTimesheetsForManagerTool(BaseTool):
    """Lists team timesheet submissions and revoke requests awaiting manager approval."""

    definition = ToolDefinition(
        name="get_pending_timesheets_for_manager",
        description="For managers and admins: retrieve all team members who submitted timesheets or requested unlocks/revokes awaiting review.",
        category="timesheet",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=["super_admin", "org_admin", "owner", "admin", "manager", "project_coordinator"],
        parameters={
            "week_date": ToolParameterSchema(
                type="string",
                description="Optional date in YYYY-MM-DD format to filter by a specific week",
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        is_admin = is_admin_user(user)

        # Find team members
        if is_admin:
            team_res = await db.execute(
                select(User).where(
                    User.organization_id == user.organization_id,
                    User.is_active == True,
                    User.is_deleted == False,
                )
            )
        else:
            team_res = await db.execute(
                select(User).where(
                    User.organization_id == user.organization_id,
                    User.reporting_manager_id == user.id,
                    User.is_active == True,
                    User.is_deleted == False,
                )
            )
        team_members = list(team_res.scalars().all())
        team_ids = [m.id for m in team_members]

        if not team_ids:
            return ToolResult(
                success=True,
                message="No direct report team members found assigned to you.",
                data={"pending_timesheets": [], "pending_unlock_requests": []},
            )

        # Query submitted time logs awaiting approval
        stmt = (
            select(ProjectTimeLog)
            .options(
                selectinload(ProjectTimeLog.user),
                selectinload(ProjectTimeLog.project),
            )
            .where(
                ProjectTimeLog.organization_id == user.organization_id,
                ProjectTimeLog.user_id.in_(team_ids),
                ProjectTimeLog.status == TimesheetStatus.SUBMITTED,
                ProjectTimeLog.is_deleted == False,
            )
        )
        if params.get("week_date"):
            try:
                w_start, w_end = get_week_bounds(date.fromisoformat(params["week_date"]))
                stmt = stmt.where(ProjectTimeLog.log_date >= w_start, ProjectTimeLog.log_date <= w_end)
            except ValueError:
                pass

        pending_logs = list((await db.execute(stmt)).scalars().all())

        # Group by user and week
        grouped_submissions: dict[str, dict[str, Any]] = {}
        for l in pending_logs:
            w_start, w_end = get_week_bounds(l.log_date)
            key = f"{l.user_id}_{w_start.isoformat()}"
            if key not in grouped_submissions:
                grouped_submissions[key] = {
                    "user_id": l.user_id,
                    "employee_name": l.user.full_name or l.user.username,
                    "email": l.user.email,
                    "week_start": w_start.isoformat(),
                    "week_end": w_end.isoformat(),
                    "total_hours": 0.0,
                    "entries_count": 0,
                }
            grouped_submissions[key]["total_hours"] += float(l.hours)
            grouped_submissions[key]["entries_count"] += 1

        # Query pending unlock/revoke requests
        unlock_res = await db.execute(
            select(TimesheetWeekUnlockRequest)
            .options(selectinload(TimesheetWeekUnlockRequest.user))
            .where(
                TimesheetWeekUnlockRequest.organization_id == user.organization_id,
                TimesheetWeekUnlockRequest.user_id.in_(team_ids),
                TimesheetWeekUnlockRequest.status == WeekUnlockStatus.PENDING,
                TimesheetWeekUnlockRequest.is_deleted == False,
            )
        )
        unlock_requests = list(unlock_res.scalars().all())
        unlock_items = [
            {
                "request_id": r.id,
                "public_id": str(r.public_id),
                "employee_name": r.user.full_name or r.user.username,
                "week_start": r.week_start_date.isoformat(),
                "request_type": r.request_type,
                "reason": r.reason,
            }
            for r in unlock_requests
        ]

        submissions_list = list(grouped_submissions.values())
        msg = (
            f"Found **{len(submissions_list)}** weekly timesheet submission(s) and "
            f"**{len(unlock_items)}** unlock/revoke request(s) awaiting your manager review."
        )

        return ToolResult(
            success=True,
            message=msg,
            data={"pending_submissions": submissions_list, "pending_requests": unlock_items},
        )


class ApproveWeeklyTimesheetTool(BaseTool):
    """Reviews and grants final weekly manager approval for an employee's timesheet."""

    definition = ToolDefinition(
        name="approve_weekly_timesheet",
        description="For managers and admins: approve or reject an employee's submitted weekly timesheet.",
        category="timesheet",
        is_read_only=False,
        requires_approval=True,
        allowed_roles=["super_admin", "org_admin", "owner", "admin", "manager"],
        parameters={
            "target_user_id": ToolParameterSchema(
                type="integer",
                description="ID of the employee whose timesheet is being reviewed",
            ),
            "week_start_date": ToolParameterSchema(
                type="string",
                description="Start date of the week (YYYY-MM-DD) being approved",
            ),
            "decision": ToolParameterSchema(
                type="string",
                description="Approval decision: 'approve' or 'reject'",
                enum=["approve", "reject"],
                default="approve",
            ),
            "note": ToolParameterSchema(
                type="string",
                description="Optional approval or rejection note",
            ),
        },
        required_parameters=["target_user_id", "week_start_date"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        target_user_id = int(params["target_user_id"])
        decision = (params.get("decision") or "approve").strip().lower()
        note = params.get("note")

        try:
            week_start = date.fromisoformat(params["week_start_date"])
        except ValueError:
            return ToolResult(success=False, message="Invalid week_start_date format. Please use YYYY-MM-DD.")

        week_start, week_end = get_week_bounds(week_start)

        # Check authorization
        target_res = await db.execute(
            select(User).where(
                User.id == target_user_id,
                User.organization_id == user.organization_id,
                User.is_deleted == False,
            )
        )
        target_user = target_res.scalar_one_or_none()
        if not target_user:
            return ToolResult(success=False, message=f"Employee ID {target_user_id} not found in your organization.")

        if not can_manage_timesheet_for(user, target_user):
            return ToolResult(
                success=False,
                message=f"Access denied: You are not the allocated reporting manager for {target_user.full_name or target_user.username}.",
            )

        # Fetch submitted logs
        logs_res = await db.execute(
            select(ProjectTimeLog).where(
                ProjectTimeLog.user_id == target_user_id,
                ProjectTimeLog.organization_id == user.organization_id,
                ProjectTimeLog.log_date >= week_start,
                ProjectTimeLog.log_date <= week_end,
                ProjectTimeLog.status == TimesheetStatus.SUBMITTED,
                ProjectTimeLog.is_deleted == False,
            )
        )
        logs = list(logs_res.scalars().all())

        if not logs:
            return ToolResult(
                success=False,
                message=f"No submitted timesheet entries found for {target_user.full_name or target_user.username} for the week of {week_start.isoformat()}.",
            )

        new_status = TimesheetStatus.APPROVED if decision == "approve" else TimesheetStatus.REJECTED
        now = datetime.now()

        for l in logs:
            l.status = new_status
            if decision == "approve":
                l.approved_by_id = user.id
                l.approved_at = now
            else:
                l.rejection_note = note

        await db.commit()

        action_word = "approved" if decision == "approve" else "rejected"
        return ToolResult(
            success=True,
            message=f"Timesheet for **{target_user.full_name or target_user.username}** for the week of **{week_start.isoformat()} to {week_end.isoformat()}** has been **{action_word.upper()}** ({len(logs)} entries).",
            data={"target_user_id": target_user.id, "week_start": week_start.isoformat(), "decision": decision, "entries_updated": len(logs)},
            records_affected=len(logs),
        )


class RequestTimesheetRevokeOrUnlockTool(BaseTool):
    """Submits a formal revoke request to modify an approved week, or unlock a locked week."""

    definition = ToolDefinition(
        name="request_timesheet_revoke_or_unlock",
        description="Request permission from your manager to revoke and re-open an approved timesheet week, or unlock an older locked week.",
        category="timesheet",
        is_read_only=False,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "week_start_date": ToolParameterSchema(
                type="string",
                description="Week start date in YYYY-MM-DD format",
            ),
            "request_type": ToolParameterSchema(
                type="string",
                description="'revoke' to modify an approved week, or 'unlock' to log time in a past locked week",
                enum=["revoke", "unlock"],
                default="revoke",
            ),
            "reason": ToolParameterSchema(
                type="string",
                description="Explanation of why the modification or unlock is necessary",
            ),
        },
        required_parameters=["week_start_date", "reason"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        reason = params["reason"].strip()
        req_type = (params.get("request_type") or "revoke").strip().lower()

        try:
            week_start = date.fromisoformat(params["week_start_date"])
        except ValueError:
            return ToolResult(success=False, message="Invalid date format. Please use YYYY-MM-DD.")

        week_start, week_end = get_week_bounds(week_start)

        req = TimesheetWeekUnlockRequest(
            organization_id=user.organization_id,
            user_id=user.id,
            week_start_date=week_start,
            week_end_date=week_end,
            request_type=req_type,
            status=WeekUnlockStatus.PENDING,
            reason=reason,
        )
        db.add(req)
        await db.commit()

        return ToolResult(
            success=True,
            message=(
                f"Your **{req_type.upper()}** request for the week of **{week_start.isoformat()} to {week_end.isoformat()}** "
                f"has been submitted to your reporting manager for approval."
            ),
            data={"request_id": req.id, "public_id": str(req.public_id), "status": req.status.value},
            records_affected=1,
        )


class GetTimesheetComplianceReportTool(BaseTool):
    """Provides agentic AI compliance audit on employee logging, missing submissions, and targets."""

    definition = ToolDefinition(
        name="get_timesheet_compliance_report",
        description="Agentic organization audit: detect missing timesheets, zero-hour workdays, unsubmitted weeks, and target deficits.",
        category="timesheet",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=["super_admin", "org_admin", "owner", "admin", "manager"],
        parameters={
            "target_week_date": ToolParameterSchema(
                type="string",
                description="Optional week date in YYYY-MM-DD format (default: current week)",
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        target_date = date.today()
        if params.get("target_week_date"):
            try:
                target_date = date.fromisoformat(params["target_week_date"])
            except ValueError:
                pass

        week_start, week_end = get_week_bounds(target_date)

        # Get all active organization users
        users_res = await db.execute(
            select(User)
            .options(selectinload(User.reporting_manager))
            .where(
                User.organization_id == user.organization_id,
                User.is_active == True,
                User.is_deleted == False,
            )
        )
        users = list(users_res.scalars().all())

        audit_results = []
        compliant_count = 0
        non_compliant_count = 0

        for u in users:
            logs_res = await db.execute(
                select(ProjectTimeLog).where(
                    ProjectTimeLog.user_id == u.id,
                    ProjectTimeLog.organization_id == user.organization_id,
                    ProjectTimeLog.log_date >= week_start,
                    ProjectTimeLog.log_date <= week_end,
                    ProjectTimeLog.is_deleted == False,
                )
            )
            logs = list(logs_res.scalars().all())
            total_hours = sum(float(l.hours) for l in logs)

            issues = []
            if total_hours == 0:
                issues.append("0 hours logged this week")
            elif total_hours < 35.0:
                issues.append(f"Below target ({round(total_hours, 1)}h logged)")

            if not u.reporting_manager_id:
                issues.append("No reporting manager allocated")

            has_unsubmitted = any(l.status == TimesheetStatus.DRAFT for l in logs)
            if has_unsubmitted and target_date > week_start:
                issues.append("Draft entries not submitted")

            status = "Non-Compliant" if issues else "Compliant"
            if issues:
                non_compliant_count += 1
            else:
                compliant_count += 1

            audit_results.append({
                "user_id": u.id,
                "name": u.full_name or u.username,
                "email": u.email,
                "manager": u.reporting_manager.full_name if u.reporting_manager else "None",
                "logged_hours": round(total_hours, 1),
                "status": status,
                "issues": issues,
            })

        summary = (
            f"### Organization Timesheet Compliance Audit ({week_start.isoformat()} to {week_end.isoformat()})\n"
            f"- **Active Staff Audited**: {len(users)}\n"
            f"- **Compliant Staff**: {compliant_count}\n"
            f"- **Staff Requiring Attention**: {non_compliant_count}\n\n"
        )

        non_compliant_list = [r for r in audit_results if r["status"] == "Non-Compliant"]
        if non_compliant_list:
            summary += "#### Issues Requiring Follow-up:\n"
            for r in non_compliant_list[:10]:
                summary += f"- **{r['name']}** ({r['email']}): {'; '.join(r['issues'])}\n"

        return ToolResult(
            success=True,
            message=summary,
            data={"total_users": len(users), "compliant": compliant_count, "non_compliant": non_compliant_count, "details": audit_results},
        )


def register_timesheet_tools() -> None:
    """Register all timesheet and attendance tools in the central MCP registry."""
    registry.register(GetMyTimesheetSummaryTool())
    registry.register(LogWorkTimeTool())
    registry.register(SubmitTimesheetTool())
    registry.register(GetPendingTimesheetsForManagerTool())
    registry.register(ApproveWeeklyTimesheetTool())
    registry.register(RequestTimesheetRevokeOrUnlockTool())
    registry.register(GetTimesheetComplianceReportTool())


register_timesheet_tools()
