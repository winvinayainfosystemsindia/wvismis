"""Organization model for multi-tenancy management"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum, Integer, JSON, Text, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class SubscriptionPlan(str, enum.Enum):
    """Organization subscription tiers"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Organization(BaseModel):
    """
    Organization (Tenant) database model.
    Maintains multi-tenant isolation, hierarchy, quotas, branding, and tenant settings.
    Parent organization: WinVinaya Infosystems
    """

    __tablename__ = "organizations"

    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        unique=True,
        index=True,
        nullable=False,
        default=uuid.uuid4,
    )

    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent organization ID for hierarchical multi-tenancy",
    )

    is_parent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="True if this is the root / parent organization (WinVinaya Infosystems)",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="URL-friendly unique tenant identifier (e.g. 'winvinaya')",
    )

    domain: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
        comment="Optional email domain for automatic tenant matching (e.g. 'winvinaya.com')",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    contact_phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, values_callable=lambda x: [e.value for e in x]),
        default=SubscriptionPlan.ENTERPRISE,
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    max_users: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
        comment="Maximum number of active users allowed in this tenant",
    )

    settings: Mapped[dict | None] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
        comment="Tenant-specific feature flags and custom configuration",
    )

    # Hierarchical parent-child relationships
    parent: Mapped[Organization | None] = relationship(
        "Organization",
        remote_side="Organization.id",
        back_populates="sub_organizations",
        lazy="selectin",
    )

    sub_organizations: Mapped[list[Organization]] = relationship(
        "Organization",
        back_populates="parent",
        lazy="selectin",
    )

    # Relationships
    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="organization",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, slug='{self.slug}', name='{self.name}')>"
