"""AI Endpoints — Credit balance, top-up purchase, usage metrics, and admin credit grants"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_superuser
from app.models.user import User
from app.models.organization import Organization
from app.schemas.ai_credit import (
    AICreditBalanceResponse,
    AICreditPurchaseRequest,
    AICreditGrantRequest,
    TokenUtilizationSummary,
)
from app.services import ai_credit_service
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/ai", tags=["AI Credits & Usage"])


async def _get_current_org(current_user: User, db: AsyncSession) -> Organization:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This account is not associated with an organization.",
        )
    org = await db.get(Organization, current_user.organization_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )
    return org


@router.get(
    "/credits",
    response_model=AICreditBalanceResponse,
    summary="Get my own AI credit balance",
)
async def get_credit_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AICreditBalanceResponse:
    org = await _get_current_org(current_user, db)
    wallet = await ai_credit_service.get_wallet_status(db, org, current_user.id)
    await db.commit()
    return AICreditBalanceResponse.from_wallet(wallet)


@router.post(
    "/credits/purchase",
    response_model=AICreditBalanceResponse,
    summary="Buy additional AI credits for my own wallet",
    description="Self-service top-up: adds credits directly to the caller's wallet.",
)
async def purchase_credits(
    payload: AICreditPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AICreditBalanceResponse:
    org = await _get_current_org(current_user, db)
    wallet = await ai_credit_service.purchase_credits_for_user(
        db, org, current_user.id, payload.amount
    )
    await db.commit()
    return AICreditBalanceResponse.from_wallet(wallet)


@router.get(
    "/usage",
    response_model=TokenUtilizationSummary,
    summary="Token utilization — totals, breakdowns, and a daily trend",
)
async def get_token_utilization(
    scope: str = Query("mine", description="'mine' for current user, 'organization' for whole tenant"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenUtilizationSummary:
    org = await _get_current_org(current_user, db)
    target_user_id = current_user.id if scope == "mine" else None
    return await ai_credit_service.get_token_utilization_summary(db, org, user_id=target_user_id)


@router.post(
    "/users/{public_id}/credits/grant",
    response_model=AICreditBalanceResponse,
    summary="Grant a user extra AI credits (Super Admin)",
)
async def grant_user_credits(
    public_id: uuid.UUID,
    payload: AICreditGrantRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
) -> AICreditBalanceResponse:
    user_repo = UserRepository(db)
    target_user = await user_repo.get_by_public_id(public_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{public_id}' not found.",
        )
    if target_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target user does not belong to an organization.",
        )

    org = await db.get(Organization, target_user.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User's organization not found.",
        )

    wallet = await ai_credit_service.grant_admin_credits_to_user(
        db, org, target_user.id, payload.amount
    )
    await db.commit()
    return AICreditBalanceResponse.from_wallet(wallet)
