"""Plan repository — raw database queries for the Plan model"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.plan import Plan, PlanTier


class PlanRepository:
    """Data access layer for Plan records."""

    @staticmethod
    async def get_by_tier(db: AsyncSession, tier: PlanTier | str) -> Optional[Plan]:
        """Return a plan by its tier, or None if not seeded yet."""
        if isinstance(tier, str):
            try:
                tier = PlanTier(tier.lower())
            except ValueError:
                return None
        result = await db.execute(select(Plan).where(Plan.tier == tier))
        return result.scalars().first()

    @staticmethod
    async def get_by_id(db: AsyncSession, plan_id: int) -> Optional[Plan]:
        """Return a plan by its internal primary key."""
        return await db.get(Plan, plan_id)

    @staticmethod
    async def list_all(db: AsyncSession) -> List[Plan]:
        """Return all plans ordered by id."""
        result = await db.execute(select(Plan).order_by(Plan.id))
        return list(result.scalars().all())
