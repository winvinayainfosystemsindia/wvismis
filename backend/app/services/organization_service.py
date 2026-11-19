"""Organization service — business logic for multi-tenancy management"""

import re
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization, SubscriptionPlan
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.repositories.organization_repository import OrganizationRepository
from app.core.config import settings


def slugify(text: str) -> str:
    """Convert organization name to URL-safe slug"""
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    return slug or "organization"


class OrganizationService:
    """Service for Organization (Tenant) business logic"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = OrganizationRepository(db)

    async def get_or_create_default_organization(self) -> Organization:
        """Fetch the default organization from settings, or create it if it does not exist."""
        default_slug = settings.DEFAULT_ORGANIZATION_SLUG.lower().strip()
        org = await self.repository.get_by_slug(default_slug)
        if org:
            return org

        org_data = {
            "name": settings.DEFAULT_ORGANIZATION_NAME,
            "slug": default_slug,
            "subscription_plan": SubscriptionPlan.ENTERPRISE,
            "is_active": True,
            "is_parent": True,
            "max_users": 100000,
            "settings": {"is_default_tenant": True, "is_parent_org": True},
        }
        return await self.repository.create(org_data)

    async def get_organization(self, org_id: int) -> Organization:
        """Get organization by ID"""
        org = await self.repository.get(org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        return org

    async def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug"""
        return await self.repository.get_by_slug(slug)

    async def list_organizations(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[List[Organization], int]:
        """List organizations with pagination and search"""
        return await self.repository.get_multi_filtered(
            skip=skip,
            limit=limit,
            is_active=is_active,
            search=search,
        )

    async def create_organization(self, org_in: OrganizationCreate) -> Organization:
        """Create a new tenant organization"""
        existing_slug = await self.repository.get_by_slug(org_in.slug)
        if existing_slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Organization slug '{org_in.slug}' is already taken",
            )

        if org_in.domain:
            existing_domain = await self.repository.get_by_domain(org_in.domain)
            if existing_domain:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Domain '{org_in.domain}' is already registered to another organization",
                )

        org_data = org_in.model_dump()
        return await self.repository.create(org_data)

    async def update_organization(
        self,
        org_id: int,
        org_in: OrganizationUpdate,
    ) -> Organization:
        """Update an existing organization"""
        org = await self.get_organization(org_id)
        update_data = org_in.model_dump(exclude_unset=True)

        if "domain" in update_data and update_data["domain"] and update_data["domain"] != org.domain:
            existing_domain = await self.repository.get_by_domain(update_data["domain"])
            if existing_domain and existing_domain.id != org.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Domain '{update_data['domain']}' is already registered",
                )

        updated = await self.repository.update(org_id, update_data)
        return updated

    async def delete_organization(self, org_id: int) -> bool:
        """Soft-delete an organization"""
        await self.get_organization(org_id)
        return await self.repository.delete(org_id, soft=True)

    async def validate_tenant_capacity(self, organization_id: int) -> Organization:
        """Verify organization is active and has not exceeded its max_users quota"""
        org = await self.get_organization(organization_id)
        if not org.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Organization '{org.name}' is currently inactive",
            )

        active_count = await self.repository.count_active_users(organization_id)
        if active_count >= org.max_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Organization '{org.name}' has reached its maximum user limit ({org.max_users})",
            )
        return org
