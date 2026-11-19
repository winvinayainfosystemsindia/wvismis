"""Base model class with common fields, timestamps, soft delete, and multi-tenancy mixins"""

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin to add soft delete functionality"""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def soft_delete(self) -> None:
        """Mark record as soft-deleted"""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None


class TenantMixin:
    """Mixin to enforce organization-level multi-tenancy on models"""

    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Multi-tenant organization owner ID",
    )


class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    """Abstract base class for all database models"""

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    def dict(self) -> dict[str, Any]:
        """Convert model columns to a dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
