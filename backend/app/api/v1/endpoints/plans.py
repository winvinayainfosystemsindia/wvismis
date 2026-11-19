"""Plan endpoints — public listing of available pricing tiers and subscription options"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_superuser
from app.models.user import User
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanResponse, PlanUpdate

router = APIRouter(prefix="/plans", tags=["Pricing & Subscription Plans"])


@router.get(
    "",
    response_model=List[PlanResponse],
    summary="List available pricing plans",
    description="Returns every seeded pricing tier with the modules it unlocks, AI monthly quota, and price.",
)
async def list_plans(db: AsyncSession = Depends(get_db)) -> List[PlanResponse]:
    """Public endpoint — no auth required, used to render pricing and billing options."""
    plans = await PlanRepository.list_all(db)
    return [PlanResponse.model_validate(plan) for plan in plans]


@router.get(
    "/{tier}",
    response_model=PlanResponse,
    summary="Get plan details by tier",
)
async def get_plan_by_tier(
    tier: str,
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    plan = await PlanRepository.get_by_tier(db, tier)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pricing plan with tier '{tier}' not found.",
        )
    return PlanResponse.model_validate(plan)


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
    return PlanResponse.model_validate(plan)
