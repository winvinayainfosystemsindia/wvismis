"""Database models registry — imported by Alembic for autogenerate support"""

from app.models.base import BaseModel, TimestampMixin, SoftDeleteMixin, TenantMixin
from app.models.organization import Organization, SubscriptionPlan
from app.models.plan import Plan, PlanTier, Module
from app.models.ai_credit import AICreditWallet, AICreditTransaction, AICreditTransactionReason
from app.models.user import User, UserRole
from app.models.token_blacklist import TokenBlacklist
from app.models.activity_log import ActivityLog, ActionType
from app.models.system_setting import SystemSetting
from app.models.ai_task_log import AITaskLog, AITaskStatus, AITaskTrigger
from app.models.ai_chat import AIChatSession, AIChatMessage
from app.models.audit import AuditLog
from app.models.project import (
    Project,
    ProjectStatus,
    BillingType,
    ProjectTask,
    ProjectTaskStatus,
    ProjectTaskFile,
    LeadPriority,
)
from app.models.timesheet import (
    TimesheetBillingType,
    TimesheetStatus,
    HolidayType,
    WeekUnlockStatus,
    UnlockRequestType,
    UserTimesheetCategory,
    OrgHoliday,
    TimesheetUserSettings,
    ProjectTimeLog,
    TimesheetWeekUnlockRequest,
)

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "Organization",
    "SubscriptionPlan",
    "Plan",
    "PlanTier",
    "Module",
    "AICreditWallet",
    "AICreditTransaction",
    "AICreditTransactionReason",
    "User",
    "UserRole",
    "TokenBlacklist",
    "ActivityLog",
    "ActionType",
    "SystemSetting",
    "AITaskLog",
    "AITaskStatus",
    "AITaskTrigger",
    "AIChatSession",
    "AIChatMessage",
    "AuditLog",
    "Project",
    "ProjectStatus",
    "BillingType",
    "ProjectTask",
    "ProjectTaskStatus",
    "ProjectTaskFile",
    "LeadPriority",
    "TimesheetBillingType",
    "TimesheetStatus",
    "HolidayType",
    "WeekUnlockStatus",
    "UserTimesheetCategory",
    "OrgHoliday",
    "TimesheetUserSettings",
    "ProjectTimeLog",
    "TimesheetWeekUnlockRequest",
]
