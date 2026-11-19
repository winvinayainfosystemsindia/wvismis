"""Plan endpoints — public listing of available pricing tiers and subscription options"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.cache import memory_cache
from app.core.websocket import ws_manager
from app.api.deps import get_current_superuser
from app.models.user import User
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanResponse, PlanUpdate

router = APIRouter(prefix="/plans", tags=["Pricing & Subscription Plans"])

CACHE_PLANS_KEY = "plans:all"
CACHE_PLANS_TTL = 600.0  # 10 minutes


@router.get(
    "",
    response_model=List[PlanResponse],
    summary="List available pricing plans",
    description="Returns every seeded pricing tier with the modules it unlocks, AI monthly quota, and price.",
)
async def list_plans(db: AsyncSession = Depends(get_db)) -> List[PlanResponse]:
    """Public endpoint — no auth required, cached for fast billing & pricing page rendering."""
    cached_plans = await memory_cache.get(CACHE_PLANS_KEY)
    if cached_plans is not None:
        return [PlanResponse.model_validate(p) for p in cached_plans]

    plans = await PlanRepository.list_all(db)
    result = [PlanResponse.model_validate(plan) for plan in plans]
    # Cache serializable dicts
    await memory_cache.set(CACHE_PLANS_KEY, [r.model_dump() for r in result], ttl_seconds=CACHE_PLANS_TTL)
    return result


@router.get(
    "/{tier}",
    response_model=PlanResponse,
    summary="Get plan details by tier",
)
async def get_plan_by_tier(
    tier: str,
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    tier_key = f"plans:tier:{tier.lower()}"
    cached_plan = await memory_cache.get(tier_key)
    if cached_plan is not None:
        return PlanResponse.model_validate(cached_plan)

    plan = await PlanRepository.get_by_tier(db, tier)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pricing plan with tier '{tier}' not found.",
        )
    result = PlanResponse.model_validate(plan)
    await memory_cache.set(tier_key, result.model_dump(), ttl_seconds=CACHE_PLANS_TTL)
    return result


@router.put(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Update plan details (Super Admin)",
)
async def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    plan = await PlanRepository.get_by_id(db, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with ID {plan_id} not found.",
        )

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, val)

    await db.commit()
    await db.refresh(plan)

    # Invalidate cache and broadcast real-time update
    await memory_cache.invalidate_prefix("plans:")
    result = PlanResponse.model_validate(plan)
    await ws_manager.broadcast_system(
        event_type="plan_updated",
        data=result.model_dump(),
    )
    return result
