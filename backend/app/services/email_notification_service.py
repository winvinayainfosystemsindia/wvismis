"""
Email Notification Service for WinVinaya MIS
============================================
Dispatches WinVinaya branded HTML notifications for timesheet submissions,
weekly manager approvals, unlock/revoke requests, project tasks, and compliance reminders.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, List, Optional

from app.core.config import settings
from app.models.user import User
from app.models.timesheet import ProjectTimeLog, TimesheetBillingType
from app.utils.email import render_template, send_email

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Enterprise email notification service coordinating templates and SMTP dispatch."""

    @staticmethod
    def _get_base_url() -> str:
        """Returns the configured frontend application URL."""
        return settings.FRONTEND_URL or "http://localhost:5173"

    @classmethod
    async def send_daily_timesheet_submission_notification(
        cls,
        manager: User,
        employee: User,
        log_date: date,
        logs: list[ProjectTimeLog],
    ) -> bool:
        """Sends daily DSR notification to the employee's reporting manager."""
        if not manager.email:
            logger.warning("Manager %s has no email address. Skipping DSR email.", manager.id)
            return False

        total_hours = sum(float(l.hours) for l in logs)
        items = []
        for l in logs:
            items.append({
                "project_name": l.project.name if getattr(l, "project", None) else None,
                "category_name": l.category.name if getattr(l, "category", None) else None,
                "task_title": l.task.title if getattr(l, "task", None) else None,
                "billing_type": l.billing_type.value if hasattr(l.billing_type, "value") else str(l.billing_type),
                "hours": float(l.hours),
                "notes": l.notes,
            })

        action_url = f"{cls._get_base_url()}/timesheets"
        subject = f"Daily Timesheet Submitted: {employee.full_name or employee.username} - {log_date.isoformat()}"

        html = render_template(
            "timesheet_daily_submission.html",
            {
                "subject": subject,
                "manager_name": manager.full_name or manager.username,
                "employee_name": employee.full_name or employee.username,
                "employee_email": employee.email,
                "log_date": log_date.strftime("%A, %B %d, %Y"),
                "total_hours": round(total_hours, 2),
                "items": items,
                "action_url": action_url,
            },
        )
        return await send_email(manager.email, subject, html)

    @classmethod
    async def send_weekly_timesheet_submission_notification(
        cls,
        manager: User,
        employee: User,
        week_start: date,
        week_end: date,
        logs: list[ProjectTimeLog],
        target_hours: float = 40.0,
    ) -> bool:
        """Sends weekly timesheet review request to the employee's reporting manager."""
        if not manager.email:
            logger.warning("Manager %s has no email address. Skipping weekly submission email.", manager.id)
            return False

        total_hours = sum(float(l.hours) for l in logs)
        billable_hours = sum(float(l.hours) for l in logs if l.billing_type == TimesheetBillingType.BILLABLE)
        non_billable_hours = total_hours - billable_hours

        # Group by day
        days_dict: dict[str, float] = {}
        for l in logs:
            d_str = l.log_date.isoformat()
            days_dict[d_str] = days_dict.get(d_str, 0.0) + float(l.hours)

        days_summary = []
        for d_str, h in sorted(days_dict.items()):
            d_obj = date.fromisoformat(d_str)
            days_summary.append({
                "date": d_str,
                "day_name": d_obj.strftime("%A"),
                "hours": round(h, 2),
            })

        action_url = f"{cls._get_base_url()}/timesheets"
        subject = f"Weekly Timesheet for Approval: {employee.full_name or employee.username} ({week_start.isoformat()} to {week_end.isoformat()})"

        html = render_template(
            "timesheet_weekly_submission.html",
            {
                "subject": subject,
                "manager_name": manager.full_name or manager.username,
                "employee_name": employee.full_name or employee.username,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_hours": round(total_hours, 2),
                "target_hours": target_hours,
                "billable_hours": round(billable_hours, 2),
                "non_billable_hours": round(non_billable_hours, 2),
                "entries_count": len(logs),
                "days": days_summary,
                "action_url": action_url,
            },
        )
        return await send_email(manager.email, subject, html)

    @classmethod
    async def send_timesheet_approval_notification(
        cls,
        employee: User,
        approver: User,
        week_start: date,
        week_end: date,
        decision: str,
        total_hours: float,
        entries_count: int,
        note: Optional[str] = None,
    ) -> bool:
        """Notifies the employee whether their timesheet was APPROVED or REJECTED."""
        if not employee.email:
            return False

        action_url = f"{cls._get_base_url()}/timesheets"
        status_word = "Approved" if decision.lower() == "approve" else "Rejected"
        subject = f"Timesheet {status_word}: Week of {week_start.isoformat()} to {week_end.isoformat()}"

        html = render_template(
            "timesheet_approval_status.html",
            {
                "subject": subject,
                "employee_name": employee.full_name or employee.username,
                "approver_name": approver.full_name or approver.username,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "decision": "approved" if decision.lower() == "approve" else "rejected",
                "total_hours": round(total_hours, 2),
                "entries_count": entries_count,
                "note": note,
                "action_url": action_url,
            },
        )
        return await send_email(employee.email, subject, html)

    @classmethod
    async def send_timesheet_unlock_request_notification(
        cls,
        manager: User,
        employee: User,
        week_start: date,
        week_end: date,
        request_type: str,
        reason: str,
    ) -> bool:
        """Sends an alert to the reporting manager for an unlock or revoke request."""
        if not manager.email:
            return False

        action_url = f"{cls._get_base_url()}/timesheets"
        subject = f"Action Required: Timesheet {request_type.upper()} Request from {employee.full_name or employee.username}"

        html = render_template(
            "timesheet_unlock_request.html",
            {
                "subject": subject,
                "manager_name": manager.full_name or manager.username,
                "employee_name": employee.full_name or employee.username,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "request_type": request_type.lower(),
                "reason": reason,
                "action_url": action_url,
            },
        )
        return await send_email(manager.email, subject, html)

    @classmethod
    async def send_timesheet_unlock_resolution_notification(
        cls,
        employee: User,
        manager: User,
        week_start: date,
        week_end: date,
        request_type: str,
        status: str,
        note: Optional[str] = None,
    ) -> bool:
        """Notifies the employee when their unlock/revoke request is approved or denied."""
        if not employee.email:
            return False

        action_url = f"{cls._get_base_url()}/timesheets"
        decision_label = "Approved" if status.lower() == "approved" else "Denied"
        subject = f"Timesheet {request_type.upper()} Request {decision_label}"

        html = render_template(
            "timesheet_unlock_resolved.html",
            {
                "subject": subject,
                "employee_name": employee.full_name or employee.username,
                "manager_name": manager.full_name or manager.username,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "request_type": request_type.lower(),
                "status": status.lower(),
                "note": note,
                "action_url": action_url,
            },
        )
        return await send_email(employee.email, subject, html)

    @classmethod
    async def send_timesheet_reminder_notification(
        cls,
        employee: User,
        week_start: date,
        week_end: date,
        total_hours: float,
        missing_days: list[str],
        target_hours: float = 40.0,
    ) -> bool:
        """Sends an automated reminder to employees with missing or incomplete timesheets."""
        if not employee.email:
            return False

        action_url = f"{cls._get_base_url()}/timesheets"
        subject = f"Timesheet Reminder: Please Submit Hours for {week_start.isoformat()} to {week_end.isoformat()}"

        html = render_template(
            "timesheet_reminder.html",
            {
                "subject": subject,
                "employee_name": employee.full_name or employee.username,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "total_hours": round(total_hours, 1),
                "target_hours": target_hours,
                "missing_days": missing_days,
                "action_url": action_url,
            },
        )
        return await send_email(employee.email, subject, html)

    @classmethod
    async def send_project_task_assignment_notification(
        cls,
        assignee: User,
        project_name: str,
        task_title: str,
        priority: str,
        due_date: Optional[str] = None,
        description: Optional[str] = None,
        estimated_hours: Optional[float] = None,
    ) -> bool:
        """Notifies a user when they are assigned a project task."""
        if not assignee.email:
            return False

        action_url = f"{cls._get_base_url()}/projects"
        subject = f"Task Assigned: {task_title} ({project_name})"

        html = render_template(
            "project_task_assignment.html",
            {
                "subject": subject,
                "assignee_name": assignee.full_name or assignee.username,
                "project_name": project_name,
                "task_title": task_title,
                "priority": priority,
                "due_date": due_date,
                "description": description,
                "estimated_hours": estimated_hours,
                "action_url": action_url,
            },
        )
        return await send_email(assignee.email, subject, html)

    @classmethod
    async def send_report_export_notification(
        cls,
        to_email: str,
        user_name: str,
        report_name: str,
        filename: str,
        file_content: bytes,
    ) -> bool:
        """Sends an export file attachment email."""
        subject = f"Your Requested Report: {report_name}"
        html = render_template(
            "report_export.html",
            {
                "subject": subject,
                "user_name": user_name,
                "report_name": report_name,
                "filename": filename,
                "generated_at": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            },
        )
        return await send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            attachments=[(filename, file_content)],
        )
