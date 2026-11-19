"""Database models registry — imported by Alembic for autogenerate support"""

from app.models.base import BaseModel, TimestampMixin, SoftDeleteMixin, TenantMixin
from app.models.organization import Organization, SubscriptionPlan
from app.models.user import User, UserRole
from app.models.token_blacklist import TokenBlacklist
from app.models.activity_log import ActivityLog, ActionType
from app.models.system_setting import SystemSetting
from app.models.ai_task_log import AITaskLog, AITaskStatus, AITaskTrigger
from app.models.ai_chat import AIChatSession, AIChatMessage

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "Organization",
    "SubscriptionPlan",
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
]
