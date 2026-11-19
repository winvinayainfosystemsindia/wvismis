"""Organization Pydantic schemas for Multi-Tenancy validation and responses"""

import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from app.models.organization import SubscriptionPlan


class OrganizationBase(BaseModel):
    """Base schema for an Organization (Tenant)"""
    name: str = Field(..., min_length=2, max_length=255, description="Organization display name")
    slug: str = Field(..., min_length=2, max_length=100, description="Unique URL-friendly identifier")
    domain: Optional[str] = Field(None, max_length=255, description="Optional domain name (e.g. winvinaya.com)")
    description: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = None
    parent_id: Optional[int] = Field(None, description="Parent organization ID for hierarchical organizations")
    is_parent: bool = Field(False, description="True if this is the root / parent organization (WinVinaya Infosystems)")
    subscription_plan: SubscriptionPlan = SubscriptionPlan.ENTERPRISE
    is_active: bool = True
    max_users: int = Field(100, ge=1, le=100000)
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        slug = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        return slug


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new Organization"""
    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an Organization"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = None
    parent_id: Optional[int] = None
    is_parent: Optional[bool] = None
    subscription_plan: Optional[SubscriptionPlan] = None
    is_active: Optional[bool] = None
    max_users: Optional[int] = Field(None, ge=1, le=100000)
    settings: Optional[Dict[str, Any]] = None


class OrganizationSummary(BaseModel):
    """Compact organization representation embedded in User responses"""
    id: int
    public_id: uuid.UUID
    name: str
    slug: str
    is_parent: bool = False
    subscription_plan: SubscriptionPlan
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class OrganizationResponse(OrganizationBase):
    """Full organization response schema"""
    id: int
    public_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedOrganizationResponse(BaseModel):
    """Paginated list of organizations"""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[OrganizationResponse]

    model_config = ConfigDict(from_attributes=True)
