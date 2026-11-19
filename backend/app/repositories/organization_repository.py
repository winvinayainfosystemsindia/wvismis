"""Organization repository for multi-tenant database operations"""

from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.models.user import User
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization (Tenant) model"""

    def __init__(self, db: AsyncSession):
        super().__init__(Organization, db)

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by unique slug"""
        query = select(Organization).where(
            Organization.slug == slug.lower().strip(),
            Organization.is_deleted == False,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_domain(self, domain: str) -> Optional[Organization]:
        """Get organization by email domain"""
        query = select(Organization).where(
            Organization.domain == domain.lower().strip(),
            Organization.is_deleted == False,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi_filtered(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[List[Organization], int]:
        """Get organizations with optional active and search filters"""
        stmt = select(Organization).where(Organization.is_deleted == False)
        count_stmt = select(func.count(Organization.id)).where(Organization.is_deleted == False)

        if is_active is not None:
            stmt = stmt.where(Organization.is_active == is_active)
            count_stmt = count_stmt.where(Organization.is_active == is_active)

        if search:
            search_filter = (
                Organization.name.ilike(f"%{search}%")
                | Organization.slug.ilike(f"%{search}%")
                | Organization.domain.ilike(f"%{search}%")
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = stmt.order_by(Organization.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def count_active_users(self, organization_id: int) -> int:
        """Count active non-deleted users belonging to an organization"""
        query = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_deleted == False,
            User.is_active == True,
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
