"""AI credit service — wallet status, balance checks, bonus grants and self-service top-ups."""

from __future__ import annotations

import math
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.organization import Organization
from app.models.ai_credit import AICreditWallet, AICreditTransactionReason
from app.repositories.ai_credit_repository import AICreditRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.ai_credit import TokenUtilizationSummary


PLAN_TIER_CREDITS = {
    "free": 100,
    "basic": 500,
    "starter": 500,
    "pro": 1000,
    "professional": 1000,
    "enterprise": 2000,
}


async def get_org_ai_credits_monthly(db: AsyncSession, org: Organization) -> int:
    """Determine how many monthly credits this organization's plan grants per user."""
    tier_name = None
    if hasattr(org, "subscription_plan") and org.subscription_plan:
        tier_name = (
            org.subscription_plan.value
            if hasattr(org.subscription_plan, "value")
            else str(org.subscription_plan)
        ).lower()

    if org.plan_id:
        plan = await PlanRepository.get_by_id(db, org.plan_id)
        if plan:
            if (str(plan.tier).lower() == "enterprise" or tier_name == "enterprise") and plan.ai_credits_monthly < 2000:
                return 2000
            if plan.ai_credits_monthly and plan.ai_credits_monthly > 0:
                return plan.ai_credits_monthly

    if tier_name:
        plan = await PlanRepository.get_by_tier(db, tier_name)
        if plan and plan.ai_credits_monthly and plan.ai_credits_monthly > 0:
            if tier_name == "enterprise" and plan.ai_credits_monthly < 2000:
                return 2000
            return plan.ai_credits_monthly
        if tier_name in PLAN_TIER_CREDITS:
            return PLAN_TIER_CREDITS[tier_name]

    return 2000 if tier_name == "enterprise" else 1000


async def get_or_create_wallet_for_user(
    db: AsyncSession, org: Organization, user_id: int
) -> AICreditWallet:
    credits_monthly = await get_org_ai_credits_monthly(db, org)
    return await AICreditRepository.get_or_create_wallet(db, org.id, user_id, credits_monthly)


async def get_wallet_status(
    db: AsyncSession, org: Organization, user_id: int
) -> AICreditWallet:
    """Read-only wallet lookup for the GET /ai/credits endpoint — auto-creates/rolls over if needed."""
    return await get_or_create_wallet_for_user(db, org, user_id)


async def purchase_credits_for_user(
    db: AsyncSession, org: Organization, user_id: int, amount: int
) -> AICreditWallet:
    wallet = await get_or_create_wallet_for_user(db, org, user_id)
    await AICreditRepository.grant_bonus_credits(
        db,
        wallet,
        amount=amount,
        user_id=user_id,
        reason=AICreditTransactionReason.PURCHASE,
    )
    return wallet


async def grant_admin_credits_to_user(
    db: AsyncSession, org: Organization, user_id: int, amount: int
) -> AICreditWallet:
    wallet = await get_or_create_wallet_for_user(db, org, user_id)
    await AICreditRepository.grant_bonus_credits(
        db,
        wallet,
        amount=amount,
        user_id=user_id,
        reason=AICreditTransactionReason.ADMIN_ADJUSTMENT,
    )
    return wallet


async def deduct_ai_credits(
    db: AsyncSession,
    org: Organization,
    user_id: int,
    cost: int = 1,
    provider: str = "openai",
    model: Optional[str] = None,
    action_type: Optional[str] = "agent_call",
    tokens_used: Optional[int] = None,
) -> AICreditWallet:
    wallet = await get_or_create_wallet_for_user(db, org, user_id)
    if wallet.balance < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AI credits exhausted for this period. Please purchase top-up credits or upgrade your plan.",
        )
    await AICreditRepository.deduct(
        db,
        wallet,
        cost=cost,
        provider=provider,
        model=model,
        action_type=action_type,
        user_id=user_id,
        tokens_used=tokens_used,
    )
    return wallet


async def get_token_utilization_summary(
    db: AsyncSession,
    org: Organization,
    user_id: Optional[int] = None,
) -> TokenUtilizationSummary:
    return await AICreditRepository.get_token_utilization(db, org.id, user_id=user_id)
