"""System setting repository for global and tenant-specific configuration"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_setting import SystemSetting
from app.repositories.base import BaseRepository


class SystemSettingRepository(BaseRepository[SystemSetting]):
    """Repository for managing system-wide and organization-scoped settings"""

    def __init__(self, db: AsyncSession):
        super().__init__(SystemSetting, db)

    async def get_by_key(
        self,
        key: str,
        organization_id: Optional[int] = None,
    ) -> Optional[SystemSetting]:
        """Get a setting by key (prefers tenant setting if organization_id is provided, falls back to global)"""
        if organization_id is not None:
            tenant_query = select(self.model).where(
                self.model.key == key,
                self.model.organization_id == organization_id,
                self.model.is_deleted == False,
            )
            tenant_res = await self.db.execute(tenant_query)
            tenant_setting = tenant_res.scalar_one_or_none()
            if tenant_setting:
                return tenant_setting

        query = select(self.model).where(
            self.model.key == key,
            self.model.organization_id.is_(None),
            self.model.is_deleted == False,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all_settings(
        self,
        organization_id: Optional[int] = None,
    ) -> List[SystemSetting]:
        """Get all system settings"""
        query = select(self.model).where(self.model.is_deleted == False)
        if organization_id is not None:
            query = query.where(
                (self.model.organization_id == organization_id)
                | (self.model.organization_id.is_(None))
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())
