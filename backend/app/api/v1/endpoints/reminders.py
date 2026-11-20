"""Reminders API endpoints for Project Tasks, Subtasks, and multi-tenant entities"""

import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.reminder import Reminder
from app.models.project import ProjectTask, Project
from app.schemas.reminder import (
    ReminderCreate,
    ReminderUpdate,
    ReminderResponse,
)
from app.services.email_notification_service import EmailNotificationService

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.get("", response_model=list[ReminderResponse], summary="List active reminders")
async def list_reminders(
    entity_type: Optional[str] = Query(None, description="e.g. project_task"),
    entity_id: Optional[int] = Query(None, description="Single entity ID"),
    entity_ids: Optional[str] = Query(None, description="Comma-separated entity IDs"),
    status: Optional[str] = Query("pending", description="Filter by status or 'all'"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch active reminders for the current user and organization."""
    query = select(Reminder).where(
        Reminder.organization_id == current_user.organization_id,
        Reminder.user_id == current_user.id,
    )

    if entity_type:
        query = query.where(Reminder.entity_type == entity_type)

    if entity_id is not None:
        query = query.where(Reminder.entity_id == entity_id)
    elif entity_ids:
        try:
            ids = [int(i.strip()) for i in entity_ids.split(",") if i.strip()]
            if ids:
                query = query.where(Reminder.entity_id.in_(ids))
        except ValueError:
            pass

    if status and status.lower() != "all":
        query = query.where(Reminder.status == status.lower())

    query = query.order_by(Reminder.remind_at.asc())
    result = await db.execute(query)
    reminders = result.scalars().all()
    return reminders


@router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED, summary="Create or update reminder")
async def create_or_update_reminder(
    payload: ReminderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sets a reminder for a project task or entity. Replaces any existing pending reminder on the same entity."""
    # Check if a pending reminder already exists on this entity for this user
    existing_query = select(Reminder).where(
        Reminder.organization_id == current_user.organization_id,
        Reminder.user_id == current_user.id,
        Reminder.entity_type == payload.entity_type,
        Reminder.entity_id == payload.entity_id,
        Reminder.status == "pending",
    )
    res = await db.execute(existing_query)
    reminder = res.scalars().first()

    if reminder:
        if not getattr(reminder, "public_id", None):
            reminder.public_id = uuid.uuid4()
        reminder.title = payload.title
        reminder.description = payload.description
        reminder.remind_at = payload.remind_at
        reminder.send_email = payload.send_email
        reminder.updated_at = datetime.now(timezone.utc)
    else:
        reminder = Reminder(
            public_id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            title=payload.title,
            description=payload.description,
            remind_at=payload.remind_at,
            status="pending",
            send_email=payload.send_email,
        )
        db.add(reminder)

    await db.commit()
    await db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}/dismiss", response_model=ReminderResponse, summary="Dismiss a reminder")
async def dismiss_reminder(
    reminder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks a reminder as dismissed."""
    query = select(Reminder).where(
        Reminder.id == reminder_id,
        Reminder.organization_id == current_user.organization_id,
        Reminder.user_id == current_user.id,
    )
    res = await db.execute(query)
    reminder = res.scalars().first()

    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    reminder.status = "dismissed"
    reminder.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_200_OK, summary="Delete a reminder")
async def delete_reminder(
    reminder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently deletes a reminder."""
    query = select(Reminder).where(
        Reminder.id == reminder_id,
        Reminder.organization_id == current_user.organization_id,
        Reminder.user_id == current_user.id,
    )
    res = await db.execute(query)
    reminder = res.scalars().first()

    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    await db.delete(reminder)
    await db.commit()
    return {"message": "Reminder deleted successfully"}


@router.post("/process-due", summary="Scan and dispatch due reminder emails")
async def process_due_reminders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processes any pending reminders that have reached their scheduled time and triggers email notifications."""
    now = datetime.now(timezone.utc)
    query = select(Reminder).options(selectinload(Reminder.user)).where(
        Reminder.organization_id == current_user.organization_id,
        Reminder.status == "pending",
        Reminder.remind_at <= now,
    )
    res = await db.execute(query)
    due_reminders = res.scalars().all()

    sent_count = 0
    for r in due_reminders:
        if r.send_email and r.user and r.user.email:
            task_title = r.title
            project_name = None
            due_date_str = None

            # Enrich from ProjectTask if applicable
            if r.entity_type == "project_task":
                task_res = await db.execute(
                    select(ProjectTask).options(selectinload(ProjectTask.project)).where(ProjectTask.id == r.entity_id)
                )
                task = task_res.scalars().first()
                if task:
                    task_title = task.title or r.title
                    if task.project:
                        project_name = task.project.name
                    if task.due_date:
                        due_date_str = task.due_date.isoformat()

            asyncio.create_task(
                EmailNotificationService.send_task_reminder_notification(
                    user=r.user,
                    task_title=task_title,
                    scheduled_time=r.remind_at.strftime("%B %d, %Y at %I:%M %p UTC"),
                    project_name=project_name,
                    due_date=due_date_str,
                    description=r.description,
                )
            )
            sent_count += 1

        r.status = "sent"
        r.sent_at = now
        r.updated_at = now

    await db.commit()
    return {"processed": len(due_reminders), "emails_dispatched": sent_count}
