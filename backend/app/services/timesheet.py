"""Timesheet business logic, daily/weekly submission, free-modification window, and lock/revoke rules.

Key rules:
1. Daily Submission & Weekly Manager Approval:
   - Employees can log and submit time entries daily (per day or upon entry) or weekly.
   - Submitting earlier days in a week never blocks logging or submitting subsequent days in that week.
   - Final approval/rejection by the reporting manager (or admin) is performed weekly.
2. Free Modification Window (Previous Day & Previous Week):
   - Employees can freely modify (edit/delete) or add to SUBMITTED, DRAFT, or REJECTED entries
     for the current week (including today and previous day) and the entire previous week
     WITHOUT manager permission, as long as the week has not received final manager approval (APPROVED).
3. Wrongly Submitted / Approved Time Revoke Request & Past-Week Unlock:
   - Once a week is APPROVED (or for weeks older than the previous week), direct modification is locked.
   - Employees can submit a Revoke Request (for wrongly submitted or approved time) or an Unlock Request
     (for unsubmitted weeks older than the previous week), which is routed to their allocated reporting
     manager or admin for approval.
   - When a manager/admin approves a Revoke Request, the week's submitted/approved entries are reset to
     DRAFT and unlocked for correction and resubmission.
"""

from datetime import date, datetime, timedelta
from typing import Optional, TYPE_CHECKING
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project, ProjectTask
from app.models.timesheet import (
    HolidayType,
    ProjectTimeLog,
    UserTimesheetCategory,
    TimesheetStatus,
    TimesheetWeekUnlockRequest,
    UnlockRequestType,
    WeekUnlockStatus,
)
from app.repositories.timesheet import (
    OrgHolidayRepository,
    ProjectTimeLogRepository,
    TimesheetCategoryRepository,
    TimesheetUserSettingsRepository,
    TimesheetWeekUnlockRequestRepository,
)
from app.middleware.exceptions import BadRequestError, ForbiddenError, NotFoundError

if TYPE_CHECKING:
    from app.models.user import User
    from app.schemas.timesheet import ProjectTimeLogCreate, ProjectTimeLogUpdate


def get_week_bounds(d: date) -> tuple[date, date]:
    """Monday..Sunday for the week containing `d`."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def get_free_edit_window_start(today: Optional[date] = None) -> date:
    """Monday of the previous week. Any date from `previous_week_monday` through `today`
    (covering the previous week, previous day, and current week) is within the free
    modification window where unapproved SUBMITTED/DRAFT/REJECTED entries can be edited
    without manager permission."""
    ref = today or date.today()
    today_monday, _ = get_week_bounds(ref)
    return today_monday - timedelta(days=7)


def is_within_free_edit_window(target_date: date, today: Optional[date] = None) -> bool:
    """Whether `target_date` is within the previous week or current week (up to today)."""
    ref = today or date.today()
    return get_free_edit_window_start(ref) <= target_date <= ref


def is_weekly_off(d: date) -> bool:
    """Sunday is always treated as a holiday, independent of the org's configured
    holiday calendar -- no OrgHoliday row needs to exist for it."""
    return d.weekday() == 6


class TimesheetLockService:
    @staticmethod
    async def check_week_access(
        db: AsyncSession, organization_id: int, user_id: int, week_start: date
    ) -> tuple[bool, Optional[TimesheetWeekUnlockRequest]]:
        """Returns (locked, active_grant). `locked=True` means the caller must block
        the action. `active_grant` is set when a past week was unlocked/revoked, so the
        caller (submit_week) can consume it once the submission actually succeeds."""
        grant = await TimesheetWeekUnlockRequestRepository.get_active_grant(
            db, organization_id, user_id, week_start
        )
        free_window_monday = get_free_edit_window_start()
        if week_start >= free_window_monday:
            return False, grant

        _, week_end = get_week_bounds(week_start)
        if await ProjectTimeLogRepository.week_has_rejected_entry(db, organization_id, user_id, week_start, week_end):
            return False, grant

        return grant is None, grant

    @staticmethod
    async def auto_grant_for_revoke(
        db: AsyncSession, *, organization_id: int, user_id: int,
        week_start: date, week_end: date, resolved_by_id: int,
    ) -> None:
        """Called when a manager revokes a wrongly-submitted/approved past week --
        creates an already-approved, unconsumed grant so resetting the entries to
        DRAFT doesn't just re-lock them behind the same wall the revoke is meant to
        clear."""
        free_window_monday = get_free_edit_window_start()
        if week_start >= free_window_monday:
            return

        existing_grant = await TimesheetWeekUnlockRequestRepository.get_active_grant(
            db, organization_id, user_id, week_start
        )
        if existing_grant:
            return

        await TimesheetWeekUnlockRequestRepository.create(
            db,
            organization_id=organization_id,
            user_id=user_id,
            week_start_date=week_start,
            week_end_date=week_end,
            request_type=UnlockRequestType.REVOKE.value,
            reason="Auto-granted: manager revoked this week's submission",
            status=WeekUnlockStatus.APPROVED,
            resolved_by_id=resolved_by_id,
            resolved_at=datetime.utcnow(),
            resolution_note="Auto-granted alongside the revoke action",
        )


def is_admin_user(user: "User") -> bool:
    """Check if the user has administrative privileges (Admin, Org Admin, Super Admin)."""
    from app.models.user import UserRole
    return bool(user.is_superuser or user.role in (UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN))


def can_manage_timesheet_for(current_user: "User", target_user: "User") -> bool:
    """Two-tier approval authorization: a user's direct reporting manager is always
    authorized, and an org ADMIN is authorized for every user org-wide as a fallback/
    escalation tier -- covering the case where the direct manager is unavailable, or
    where a user (e.g. a manager themselves) has no reporting_manager_id set at all.
    Managers still only ever see/act on their own direct reports."""
    return target_user.reporting_manager_id == current_user.id or is_admin_user(current_user)


class TimesheetService:
    # Applied when a user has no weekly_hours_target override set (TimesheetUserSettings).
    DEFAULT_WEEKLY_HOURS_TARGET = 40.0

    @staticmethod
    async def bulk_approve_week(
        db: AsyncSession, current_user: "User", user_ids: list[int], start_date: date, end_date: date,
    ) -> dict:
        """Approves the given week for every listed user this approver is authorized
        for (their direct reports, or -- for an admin -- anyone org-wide); anyone else
        in the list is silently skipped rather than failing the whole batch, so one
        stray id (e.g. a stale row from a slow-refreshing UI) doesn't block the rest."""
        from app.repositories.user import UserRepository

        approved_user_ids: list[int] = []
        skipped_user_ids: list[int] = []
        total_approved_count = 0

        for user_id in user_ids:
            target_user = await UserRepository.get_by_id(db, user_id)
            if not target_user or not can_manage_timesheet_for(current_user, target_user):
                skipped_user_ids.append(user_id)
                continue

            count = await ProjectTimeLogRepository.approve_reject_week(
                db, organization_id=current_user.organization_id, user_id=user_id,
                start_date=start_date, end_date=end_date,
                status=TimesheetStatus.APPROVED, approved_by_id=current_user.id,
            )
            if count == 0:
                skipped_user_ids.append(user_id)
                continue

            approved_user_ids.append(user_id)
            total_approved_count += count

        return {
            "approved_user_ids": approved_user_ids,
            "skipped_user_ids": skipped_user_ids,
            "total_approved_count": total_approved_count,
        }

    @staticmethod
    async def get_team_settings(db: AsyncSession, current_user: "User") -> list[dict]:
        """Per-person weekly_hours_target (and other settings) for everyone the
        current user can manage -- their direct reports, or org-wide for an admin --
        so the team-approvals UI can flag overtime without an N+1 settings fetch."""
        from app.models.user import User, UserRole

        if is_admin_user(current_user):
            result = await db.execute(
                select(User).where(User.organization_id == current_user.organization_id, User.is_deleted.is_(False))
            )
        else:
            result = await db.execute(
                select(User).where(
                    User.reporting_manager_id == current_user.id, User.is_deleted.is_(False),
                )
            )
        team = list(result.scalars().all())
        if not team:
            return []

        settings_rows = await TimesheetUserSettingsRepository.list_for_users(
            db, current_user.organization_id, [u.id for u in team]
        )
        settings_by_user = {s.user_id: s for s in settings_rows}

        return [
            {
                "id": settings_by_user[u.id].id if u.id in settings_by_user else 0,
                "user_id": u.id,
                "user_name": u.full_name or u.email,
                "can_log_on_holidays": settings_by_user[u.id].can_log_on_holidays if u.id in settings_by_user else False,
                "max_retroactive_days": settings_by_user[u.id].max_retroactive_days if u.id in settings_by_user else None,
                "weekly_hours_target": float(settings_by_user[u.id].weekly_hours_target) if u.id in settings_by_user and settings_by_user[u.id].weekly_hours_target is not None else None,
                "created_at": settings_by_user[u.id].created_at if u.id in settings_by_user else u.created_at,
                "updated_at": settings_by_user[u.id].updated_at if u.id in settings_by_user else u.updated_at,
            }
            for u in team
        ]

    @staticmethod
    async def _validate_log_target(
        db: AsyncSession,
        organization_id: int,
        project_id: Optional[int],
        task_id: Optional[int],
        category_id: Optional[int],
        notes: Optional[str],
    ) -> Optional[UserTimesheetCategory]:
        """Validates project/task vs general category exclusivity, project status,
        task ownership, and mandatory notes on 'Other' category."""
        if project_id is not None and category_id is not None:
            raise BadRequestError("A time entry must be logged against either a Project/Task or a General Category, not both.")
        if project_id is None and category_id is None:
            raise BadRequestError("Please select either a Project/Task or a General Category for this time entry.")
        if task_id is not None and project_id is None:
            raise BadRequestError("A task cannot be selected without a project.")

        if project_id is not None:
            proj = await db.get(Project, project_id)
            if not proj or proj.organization_id != organization_id or getattr(proj, "is_deleted", False):
                raise NotFoundError("Project not found")
            proj_status = getattr(proj.status, "value", str(proj.status)).lower() if getattr(proj, "status", None) else ""
            if proj_status in ("cancelled", "archived"):
                raise BadRequestError(f"Cannot log time against a {proj_status} project ({proj.name}).")
            if task_id is not None:
                tsk = await db.get(ProjectTask, task_id)
                if not tsk or tsk.project_id != project_id or getattr(tsk, "is_deleted", False):
                    raise NotFoundError("Task not found under the selected project")
            return None

        category = await TimesheetCategoryRepository.get_by_id(db, category_id)  # type: ignore[arg-type]
        if not category or category.organization_id != organization_id:
            raise NotFoundError("Timesheet category not found")
        if category.name.strip().lower() == "other" and (not notes or not notes.strip()):
            raise BadRequestError("Notes/description are required when logging time under the 'Other' category.")
        return category

    @staticmethod
    async def _validate_date_and_holiday(
        db: AsyncSession,
        organization_id: int,
        user_id: int,
        target_date: date,
        category: Optional[UserTimesheetCategory],
        has_active_grant: bool = False,
    ) -> bool:
        """Validates future date block, retroactive limit, blackout days, and holiday/Sunday overrides.
        Returns `is_holiday_override`."""
        today = date.today()
        if target_date > today:
            raise BadRequestError("Future time logging is blocked by default configuration")

        user_settings = await TimesheetUserSettingsRepository.get_by_user(db, organization_id, user_id)
        max_days = user_settings.max_retroactive_days if user_settings.max_retroactive_days is not None else 30
        if not has_active_grant and (today - target_date).days > max_days:
            raise BadRequestError(f"Cannot log time older than {max_days} days retroactively")

        holiday = await OrgHolidayRepository.check_date(db, organization_id, target_date)
        is_holiday_override = False
        if holiday and holiday.type == HolidayType.BLACKOUT:
            if category and category.name.strip().lower() == "leave":
                raise BadRequestError(f"Leave cannot be logged on a Blackout working day ({holiday.name}).")
        elif holiday or is_weekly_off(target_date):
            if not user_settings.can_log_on_holidays:
                reason = holiday.name if holiday else "Sunday"
                raise BadRequestError(f"Logging time on holidays is blocked ({reason}). Contact your manager for override access.")
            is_holiday_override = True

        return is_holiday_override

    @staticmethod
    async def create_time_log(
        db: AsyncSession, current_user: "User", payload: "ProjectTimeLogCreate"
    ) -> ProjectTimeLog:
        """Logs a new time entry, supporting daily submission and free modification for
        the current week and previous week while enforcing all enterprise constraints."""
        week_start, week_end = get_week_bounds(payload.log_date)

        # Validation 1: Approved week block -- once a week has received final weekly
        # approval by the manager, no new entries can be added unless revoked.
        has_approved = await ProjectTimeLogRepository.week_has_approved_entry(
            db, current_user.organization_id, current_user.id, week_start, week_end
        )
        if has_approved:
            raise BadRequestError(
                "This week has already received final approval from your manager. "
                "Submit a Revoke Request to your allocated manager or admin to make changes."
            )

        # Validation 1.5: Past-week lock (applies only to weeks older than the previous week
        # unless an active unlock/revoke grant exists). Current week and previous week are open.
        locked, active_grant = await TimesheetLockService.check_week_access(
            db, current_user.organization_id, current_user.id, week_start
        )
        if locked:
            raise BadRequestError(
                f"The week of {week_start.isoformat()} has already ended and is locked. "
                "Request an unlock or revoke from your manager to add entries for that week."
            )

        # If this is an older week (outside the free edit window) that already has SUBMITTED
        # entries and no active revoke/unlock grant, block adding new entries without a revoke request.
        if not is_within_free_edit_window(payload.log_date) and active_grant is None:
            has_submitted = await ProjectTimeLogRepository.week_has_submitted_entry(
                db, current_user.organization_id, current_user.id, week_start, week_end
            )
            if has_submitted:
                raise BadRequestError(
                    f"The week of {week_start.isoformat()} is already submitted and outside the previous-week modification window. "
                    "Submit a Revoke Request to your reporting manager or admin to modify it."
                )

        # Validation 2: Target exclusivity & project/category validity
        category = await TimesheetService._validate_log_target(
            db, current_user.organization_id,
            payload.project_id, payload.task_id, payload.category_id, payload.notes,
        )

        # Validation 3: Date, retroactive limit & holiday/blackout checks
        is_holiday_override = await TimesheetService._validate_date_and_holiday(
            db, current_user.organization_id, current_user.id,
            payload.log_date, category, has_active_grant=active_grant is not None,
        )

        # Validation 4: 24 Hours daily cap verification
        current_day_total = await ProjectTimeLogRepository.get_day_total_hours(
            db, current_user.organization_id, current_user.id, payload.log_date
        )
        if current_day_total + payload.hours > 24.0:
            raise BadRequestError(f"Logging {payload.hours}h would exceed the maximum limit of 24 hours per day (already logged {current_day_total}h)")

        # Validation 5: Duplicate entry prevention
        existing = await ProjectTimeLogRepository.find_existing_entry(
            db, current_user.organization_id, current_user.id, payload.log_date,
            payload.project_id, payload.task_id, payload.category_id, payload.billing_type
        )
        if existing:
            target_desc = "this task" if payload.task_id else "this project" if payload.project_id else "this category"
            raise BadRequestError(
                f"You already have a time entry for {target_desc} on {payload.log_date.isoformat()}. "
                "Edit the existing entry instead of adding a new one."
            )

        # Optional direct daily submission on create
        initial_status = TimesheetStatus.DRAFT
        if getattr(payload, "submit", False):
            if current_user.reporting_manager_id is None:
                raise BadRequestError("You cannot submit timesheets without an assigned Reporting Manager.")
            initial_status = TimesheetStatus.SUBMITTED

        log = await ProjectTimeLogRepository.create(
            db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            project_id=payload.project_id,
            task_id=payload.task_id,
            category_id=payload.category_id,
            log_date=payload.log_date,
            hours=payload.hours,
            notes=payload.notes,
            billing_type=payload.billing_type,
            is_holiday_override=is_holiday_override,
            status=initial_status,
        )
        await db.commit()

        result = await db.execute(
            select(ProjectTimeLog)
            .options(
                selectinload(ProjectTimeLog.project),
                selectinload(ProjectTimeLog.task),
                selectinload(ProjectTimeLog.category),
                selectinload(ProjectTimeLog.user),
            )
            .where(ProjectTimeLog.id == log.id)
        )
        return result.scalar_one()

    @staticmethod
    async def update_time_log(
        db: AsyncSession, current_user: "User", log_id: int, payload: "ProjectTimeLogUpdate"
    ) -> ProjectTimeLog:
        """Updates a time entry. Allows modifying DRAFT, REJECTED, and SUBMITTED entries
        for the current week (including today and previous day) and previous week without
        manager permission. Approved entries or entries older than the previous week
        require a manager-approved Revoke/Unlock Request."""
        log = await ProjectTimeLogRepository.get_by_id(db, log_id)
        if not log or log.organization_id != current_user.organization_id:
            raise NotFoundError("Time log entry not found")

        if log.user_id != current_user.id:
            raise ForbiddenError("You cannot modify other users' time logs")

        if log.status == TimesheetStatus.APPROVED:
            raise BadRequestError(
                "Approved timesheet entries cannot be modified directly. "
                "Please submit a Revoke Request to your allocated reporting manager or admin."
            )

        fields_set = payload.model_fields_set
        target_project_id = payload.project_id if "project_id" in fields_set else log.project_id
        target_task_id = payload.task_id if "task_id" in fields_set else log.task_id
        target_category_id = payload.category_id if "category_id" in fields_set else log.category_id
        target_log_date = payload.log_date if "log_date" in fields_set and payload.log_date is not None else log.log_date
        target_billing_type = payload.billing_type if "billing_type" in fields_set and payload.billing_type is not None else log.billing_type
        target_notes = payload.notes if "notes" in fields_set else log.notes
        target_hours = payload.hours if "hours" in fields_set and payload.hours is not None else float(log.hours)

        orig_week_start, _ = get_week_bounds(log.log_date)
        target_week_start, target_week_end = get_week_bounds(target_log_date)

        # Ensure destination week is not already APPROVED
        if await ProjectTimeLogRepository.week_has_approved_entry(
            db, current_user.organization_id, current_user.id, target_week_start, target_week_end
        ):
            raise BadRequestError(
                "This week has already received final approval from your manager. "
                "Submit a Revoke Request to your allocated manager or admin to make changes."
            )

        active_grant = await TimesheetWeekUnlockRequestRepository.get_active_grant(
            db, current_user.organization_id, current_user.id, target_week_start
        )

        if log.status == TimesheetStatus.SUBMITTED:
            # Free modification allowed for previous day, current week, and previous week
            if not (is_within_free_edit_window(log.log_date) and is_within_free_edit_window(target_log_date)):
                orig_grant = await TimesheetWeekUnlockRequestRepository.get_active_grant(
                    db, current_user.organization_id, current_user.id, orig_week_start
                )
                if orig_grant is None or active_grant is None:
                    raise BadRequestError(
                        "Submitted timesheets older than the previous week cannot be modified without manager permission. "
                        "Please submit a Revoke Request to your allocated reporting manager or admin."
                    )
        elif log.status == TimesheetStatus.DRAFT:
            locked, grant = await TimesheetLockService.check_week_access(
                db, current_user.organization_id, current_user.id, target_week_start
            )
            if locked:
                raise BadRequestError(
                    f"The week of {target_week_start.isoformat()} has already ended and is locked. "
                    "Request access from your manager to edit entries for that week."
                )
            active_grant = grant

        # Validate target exclusivity & project/category validity
        category = await TimesheetService._validate_log_target(
            db, current_user.organization_id,
            target_project_id, target_task_id, target_category_id, target_notes,
        )

        # Validate date, retroactive limit & holiday/blackout checks
        is_holiday_override = await TimesheetService._validate_date_and_holiday(
            db, current_user.organization_id, current_user.id,
            target_log_date, category, has_active_grant=active_grant is not None,
        )

        # Validate 24 Hours cap on target_log_date
        current_day_total = await ProjectTimeLogRepository.get_day_total_hours(
            db, current_user.organization_id, current_user.id, target_log_date, exclude_log_id=log.id
        )
        if current_day_total + target_hours > 24.0:
            raise BadRequestError(f"Logging {target_hours}h would exceed the maximum limit of 24 hours per day (already logged {current_day_total}h)")

        # Duplicate entry prevention
        existing = await ProjectTimeLogRepository.find_existing_entry(
            db, current_user.organization_id, current_user.id, target_log_date,
            target_project_id, target_task_id, target_category_id, target_billing_type, exclude_log_id=log.id
        )
        if existing:
            target_desc = "this task" if target_task_id else "this project" if target_project_id else "this category"
            raise BadRequestError(
                f"You already have a time entry for {target_desc} on {target_log_date.isoformat()}. "
                "Edit that entry instead of creating a duplicate."
            )

        update_kwargs = payload.model_dump(exclude_unset=True)
        update_kwargs["is_holiday_override"] = is_holiday_override
        updated = await ProjectTimeLogRepository.update(db, log, **update_kwargs)
        await db.commit()
        result = await db.execute(
            select(ProjectTimeLog)
            .options(
                selectinload(ProjectTimeLog.project),
                selectinload(ProjectTimeLog.task),
                selectinload(ProjectTimeLog.category),
                selectinload(ProjectTimeLog.user),
            )
            .where(ProjectTimeLog.id == updated.id)
        )
        return result.scalar_one()

    @staticmethod
    async def delete_time_log(db: AsyncSession, current_user: "User", log_id: int) -> None:
        """Soft-deletes a time entry. Allows deleting DRAFT, REJECTED, and SUBMITTED entries
        within the current week (including previous day) and previous week without manager
        permission. Approved entries or entries older than the previous week require a
        manager-approved Revoke/Unlock Request."""
        log = await ProjectTimeLogRepository.get_by_id(db, log_id)
        if not log or log.organization_id != current_user.organization_id:
            raise NotFoundError("Time log entry not found")

        if log.user_id != current_user.id:
            raise ForbiddenError("You cannot delete other users' time logs")

        if log.status == TimesheetStatus.APPROVED:
            raise BadRequestError(
                "Approved timesheet entries cannot be deleted directly. "
                "Please submit a Revoke Request to your allocated reporting manager or admin."
            )

        week_start, week_end = get_week_bounds(log.log_date)
        if await ProjectTimeLogRepository.week_has_approved_entry(
            db, current_user.organization_id, current_user.id, week_start, week_end
        ):
            raise BadRequestError(
                "This week has already received final approval from your manager. "
                "Submit a Revoke Request to your allocated manager or admin to make changes."
            )

        if log.status == TimesheetStatus.SUBMITTED:
            if not is_within_free_edit_window(log.log_date):
                grant = await TimesheetWeekUnlockRequestRepository.get_active_grant(
                    db, current_user.organization_id, current_user.id, week_start
                )
                if grant is None:
                    raise BadRequestError(
                        "Submitted timesheets older than the previous week cannot be deleted without manager permission. "
                        "Please submit a Revoke Request to your allocated reporting manager or admin."
                    )
        elif log.status == TimesheetStatus.DRAFT:
            locked, _ = await TimesheetLockService.check_week_access(
                db, current_user.organization_id, current_user.id, week_start
            )
            if locked:
                raise BadRequestError(
                    f"The week of {week_start.isoformat()} has already ended and is locked. "
                    "Request access from your manager to delete entries for that week."
                )

        await ProjectTimeLogRepository.delete(db, log)
        await db.commit()

    @staticmethod
    async def submit_daily_timesheet(
        db: AsyncSession, current_user: "User", log_date: date
    ) -> int:
        """Submits all draft/rejected time entries for a single day (`log_date`) to the
        reporting manager. Final approval by the manager remains weekly."""
        if current_user.reporting_manager_id is None:
            raise BadRequestError("You cannot submit timesheets without an assigned Reporting Manager.")

        if log_date > date.today():
            raise BadRequestError("Cannot submit timesheets for a future date.")

        week_start, _ = get_week_bounds(log_date)
        locked, _ = await TimesheetLockService.check_week_access(
            db, current_user.organization_id, current_user.id, week_start
        )
        if locked:
            raise BadRequestError(
                f"The week of {week_start.isoformat()} has already ended and is locked for "
                "submission. Request access from your manager to submit it."
            )

        rowcount = await ProjectTimeLogRepository.submit_day(
            db, organization_id=current_user.organization_id, user_id=current_user.id, log_date=log_date
        )
        if rowcount == 0:
            raise BadRequestError(f"No draft or rejected time entries found to submit for {log_date.isoformat()}")

        await db.commit()
        return rowcount

    @staticmethod
    async def submit_weekly_timesheet(
        db: AsyncSession, current_user: "User", start_date: date, end_date: date
    ) -> int:
        """Submits draft/rejected time entries in a week to the reporting manager --
        extracted out of POST /timesheets/submit-week. Returns the submitted count."""
        if current_user.reporting_manager_id is None:
            raise BadRequestError("You cannot submit timesheets without an assigned Reporting Manager. Set one in your Profile Settings.")

        # Past-week lock -- weeks older than the previous week can only be submitted if
        # the manager granted an unlock/revoke request for it.
        locked, grant = await TimesheetLockService.check_week_access(
            db, current_user.organization_id, current_user.id, start_date
        )
        if locked:
            raise BadRequestError(
                f"The week of {start_date.isoformat()} has already ended and is locked for "
                "submission. Request access from your manager to submit it."
            )

        rowcount = await ProjectTimeLogRepository.submit_week(
            db, organization_id=current_user.organization_id, user_id=current_user.id,
            start_date=start_date, end_date=end_date
        )
        if rowcount == 0:
            raise BadRequestError("No draft or rejected time entries found to submit for the selected week")

        # Consume an unlock grant once a locked older week is submitted.
        if grant is not None and start_date < get_free_edit_window_start():
            await TimesheetWeekUnlockRequestRepository.consume(db, grant)

        await db.commit()
        return rowcount

    @staticmethod
    async def request_week_unlock(
        db: AsyncSession,
        current_user: "User",
        week_start_date: date,
        week_end_date: date,
        reason: Optional[str] = None,
        request_type: UnlockRequestType = UnlockRequestType.UNLOCK,
    ) -> TimesheetWeekUnlockRequest:
        """Submits either:
        - A REVOKE request (`request_type=REVOKE`): asks the allocated reporting manager
          or admin to revoke a wrongly submitted or already approved week back to DRAFT.
        - An UNLOCK request (`request_type=UNLOCK`): asks the allocated reporting manager
          or admin to unlock an older past week that ended without being submitted."""
        if current_user.reporting_manager_id is None:
            raise BadRequestError("You cannot submit a request without an assigned Reporting Manager.")

        week_start, week_end = get_week_bounds(week_start_date)
        if week_end != week_end_date:
            raise BadRequestError("week_start_date and week_end_date must be the Monday and Sunday of the same week")

        existing = await TimesheetWeekUnlockRequestRepository.get_pending_for_week(
            db, current_user.organization_id, current_user.id, week_start
        )
        if existing:
            raise BadRequestError("You already have a pending request for this week")

        has_sub_or_app = await ProjectTimeLogRepository.week_has_submitted_or_approved_entry(
            db, current_user.organization_id, current_user.id, week_start, week_end
        )

        # Auto-promote to REVOKE if the week has submitted/approved entries
        effective_type = UnlockRequestType.REVOKE if (request_type == UnlockRequestType.REVOKE or has_sub_or_app) else UnlockRequestType.UNLOCK

        if effective_type == UnlockRequestType.REVOKE:
            if not has_sub_or_app:
                raise BadRequestError("There are no submitted or approved time entries in this week to revoke.")
            if not reason or not reason.strip():
                raise BadRequestError("A reason is required when requesting to revoke a wrongly submitted timesheet.")
        else:
            free_window_monday = get_free_edit_window_start()
            if week_start >= free_window_monday:
                raise BadRequestError(
                    "Current week and previous week timesheets are open for editing and submission without manager permission."
                )
            active_grant = await TimesheetWeekUnlockRequestRepository.get_active_grant(
                db, current_user.organization_id, current_user.id, week_start
            )
            if active_grant:
                raise BadRequestError("This week is already unlocked -- you can edit and submit it now")

        req = await TimesheetWeekUnlockRequestRepository.create(
            db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            week_start_date=week_start,
            week_end_date=week_end,
            request_type=effective_type.value,
            reason=reason.strip() if reason else None,
        )
        await db.commit()
        return req
