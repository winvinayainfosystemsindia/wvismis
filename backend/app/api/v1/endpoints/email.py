"""
Email Configuration & Notification Endpoints
============================================
Provides diagnostic status, test email sending, and timesheet reminder dispatching.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.timesheet import ProjectTimeLog
from app.services.timesheet import get_week_bounds
from app.utils.email import verify_smtp_connection, send_email, render_template
from app.services.email_notification_service import EmailNotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


class EmailStatusResponse(BaseModel):
    configured: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_tls: bool
    from_email: str
    from_name: str
    connection_test: Optional[dict[str, Any]] = None


class EmailTestRequest(BaseModel):
    recipient_email: Optional[EmailStr] = None


class EmailTestResponse(BaseModel):
    success: bool
    message: str
    recipient: str


class RemindTimesheetRequest(BaseModel):
    target_week_date: Optional[date] = None


class RemindTimesheetResponse(BaseModel):
    success: bool
    reminders_sent: int
    recipients: list[str]
    message: str


@router.get("/status", response_model=EmailStatusResponse, summary="Check SMTP Email Configuration")
async def get_email_status(
    current_user: User = Depends(deps.get_current_active_user),
) -> EmailStatusResponse:
    """Returns the current SMTP setup and tests live server connectivity."""
    conn = await verify_smtp_connection()
    return EmailStatusResponse(
        configured=bool(settings.SMTP_HOST and settings.SMTP_USER),
        smtp_host=settings.SMTP_HOST or "",
        smtp_port=int(settings.SMTP_PORT or 587),
        smtp_user=settings.SMTP_USER or "",
        smtp_tls=bool(settings.SMTP_TLS),
        from_email=settings.EMAILS_FROM_EMAIL or "",
        from_name=settings.EMAILS_FROM_NAME or "",
        connection_test=conn,
    )


@router.post("/test", response_model=EmailTestResponse, summary="Send a test verification email")
async def send_test_email(
    payload: EmailTestRequest,
    current_user: User = Depends(deps.get_current_active_user),
) -> EmailTestResponse:
    """Sends a verification email to the user's email or specified address."""
    to_email = payload.recipient_email or current_user.email
    if not to_email:
        raise HTTPException(status_code=400, detail="Recipient email must be provided or set on user profile.")

    subject = "WinVinaya MIS - Email Configuration Verified"
    html_content = render_template(
        "base_email.html",
        {
            "subject": subject,
        },
    )
    # Wrap with a test message body
    test_body = f"""
    <h2>Email System Verification</h2>
    <p>Hello <strong>{current_user.full_name or current_user.username}</strong>,</p>
    <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 16px; border-radius: 6px; margin: 20px 0;">
        <p style="margin: 0; color: #166534; font-weight: 600;">
            ✅ Your WinVinaya MIS email configuration is working successfully!
        </p>
    </div>
    <p>
        SMTP Host: <code>{settings.SMTP_HOST}:{settings.SMTP_PORT}</code><br/>
        From Address: <code>{settings.EMAILS_FROM_NAME} &lt;{settings.EMAILS_FROM_EMAIL}&gt;</code>
    </p>
    """
    full_html = html_content.replace(
        '<div class="content">\n                \n            </div>',
        f'<div class="content">{test_body}</div>'
    )
    if '<div class="content">' in full_html and test_body not in full_html:
        full_html = render_template(
            "report_export.html",
            {
                "user_name": current_user.full_name or current_user.username,
                "report_name": "SMTP Configuration Test",
                "filename": "smtp_test_report.txt",
                "generated_at": date.today().isoformat(),
            }
        )

    sent = await send_email(to_email=to_email, subject=subject, html_content=full_html)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to deliver test email via SMTP server. Check server logs.")

    return EmailTestResponse(
        success=True,
        message="Test email dispatched successfully.",
        recipient=to_email,
    )


@router.post("/remind-timesheets", response_model=RemindTimesheetResponse, summary="Send timesheet reminder to team")
async def trigger_timesheet_reminders(
    payload: RemindTimesheetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> RemindTimesheetResponse:
    """Managers/Admins: send email reminders to employees with missing or incomplete timesheets."""
    target_date = payload.target_week_date or date.today()
    week_start, week_end = get_week_bounds(target_date)

    is_admin = current_user.role in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.OWNER, UserRole.ADMIN)

    stmt = select(User).where(
        User.organization_id == current_user.organization_id,
        User.is_active == True,
        User.is_deleted == False,
    )
    if not is_admin:
        stmt = stmt.where(User.reporting_manager_id == current_user.id)

    users = list((await db.execute(stmt)).scalars().all())

    recipients_sent = []
    for u in users:
        if not u.email:
            continue
        logs_res = await db.execute(
            select(ProjectTimeLog).where(
                ProjectTimeLog.user_id == u.id,
                ProjectTimeLog.organization_id == current_user.organization_id,
                ProjectTimeLog.log_date >= week_start,
                ProjectTimeLog.log_date <= week_end,
                ProjectTimeLog.is_deleted == False,
            )
        )
        logs = list(logs_res.scalars().all())
        total_hours = sum(float(l.hours) for l in logs)

        if total_hours < 35.0:
            # Calculate missing workdays
            logged_dates = {l.log_date for l in logs if float(l.hours) > 0}
            missing_days = []
            cur = week_start
            while cur <= min(week_end, date.today()):
                if cur.weekday() < 5 and cur not in logged_dates:
                    missing_days.append(cur.strftime("%A (%b %d)"))
                cur += date.resolution

            background_tasks.add_task(
                EmailNotificationService.send_timesheet_reminder_notification,
                employee=u,
                week_start=week_start,
                week_end=week_end,
                total_hours=total_hours,
                missing_days=missing_days,
                target_hours=40.0,
            )
            recipients_sent.append(u.email)

    return RemindTimesheetResponse(
        success=True,
        reminders_sent=len(recipients_sent),
        recipients=recipients_sent,
        message=f"Dispatched {len(recipients_sent)} timesheet reminder email(s) in background.",
    )
