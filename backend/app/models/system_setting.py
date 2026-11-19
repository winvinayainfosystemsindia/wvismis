"""System setting model for application-wide and tenant-level configurations"""

from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel, TenantMixin


class SystemSetting(BaseModel, TenantMixin):
    """
    Model for storing system-wide or organization-specific settings.
    Used for AI Harness configuration, runtime overrides, etc.
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
