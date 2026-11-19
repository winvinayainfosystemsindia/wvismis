"""User model with multi-tenant organization link and RBAC roles"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum, Integer, ForeignKey, Uuid, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TenantMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class UserRole(str, enum.Enum):
    """User role enumeration for WVISMIS multi-tenant RBAC"""
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SOURCING = "sourcing"
    TRAINER = "trainer"
    COUNSELOR = "counselor"
    PLACEMENT = "placement"
    PROJECT_COORDINATOR = "project_coordinator"
    DEVELOPER = "developer"
    USER = "user"


class User(BaseModel, TenantMixin):
    """User database model scoped to an Organization (Tenant)"""

    __tablename__ = "users"

    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        unique=True,
        index=True,
        nullable=False,
        default=uuid.uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        nullable=False,
        index=True,
    )

    mobile: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    designation: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Every user MUST be associated with an organization (parent or tenant org)
    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated organization ID (cannot be null; defaults to parent org)",
    )

    # Multi-tenant Organization relationship
    organization: Mapped[Organization] = relationship(
        "Organization",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, email='{self.email}', role='{self.role.value}', "
            f"org_id={self.organization_id})>"
        )
