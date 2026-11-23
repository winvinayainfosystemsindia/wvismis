"""AI Endpoints — Credit balance, top-up purchase, usage metrics, and admin credit grants with in-memory caching and real-time WebSockets"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.cache import memory_cache
from app.core.websocket import ws_manager
from app.api.deps import get_current_user, get_current_superuser
from app.models.user import User, UserRole
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

CREDIT_CACHE_TTL = 30.0  # 30 seconds TTL for fast repeated page loads
USAGE_CACHE_TTL = 30.0


async def _get_current_org(current_user: User, db: AsyncSession) -> Organization:
    if current_user.organization_id is None:
        if current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN:
            stmt = select(Organization).where(Organization.is_deleted == False)
            first_org = (await db.execute(stmt)).scalars().first()
            if first_org:
                return first_org
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This account is not associated with an organization.",
        )
    org = await db.get(Organization, current_user.organization_id)
    if org is None:
        if current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN:
            stmt = select(Organization).where(Organization.is_deleted == False)
            first_org = (await db.execute(stmt)).scalars().first()
            if first_org:
                return first_org
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
    cache_key = f"credits:{current_user.id}"
    cached_data = await memory_cache.get(cache_key)
    if cached_data is not None:
        return AICreditBalanceResponse.model_validate(cached_data)

    try:
        org = await _get_current_org(current_user, db)
        wallet = await ai_credit_service.get_wallet_status(db, org, current_user.id)
        await db.commit()
        res = AICreditBalanceResponse.from_wallet(wallet)
    except HTTPException:
        # Fallback for accounts without an organization (e.g. system superuser):
        # return enterprise tier default balance (2000) so the client UI navbar always displays credits cleanly
        res = AICreditBalanceResponse(
            balance=2000,
            granted=2000,
            period_start=datetime.now(timezone.utc),
            percent_used=0.0,
        )

    await memory_cache.set(cache_key, res.model_dump(), ttl_seconds=CREDIT_CACHE_TTL)
    return res


@router.post(
    "/credits/purchase",
    response_model=AICreditBalanceResponse,
    summary="Buy additional AI credits for my own wallet",
    description="Self-service top-up: adds credits directly to the caller's wallet and broadcasts real-time balance update.",
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
    res = AICreditBalanceResponse.from_wallet(wallet)

    # Invalidate cached credit & usage
    await memory_cache.delete(f"credits:{current_user.id}")
    await memory_cache.invalidate_prefix(f"usage:{org.id}")

    # Broadcast real-time WebSocket event to all connections of this user
    await ws_manager.send_to_user(
        user_id=current_user.id,
        event_type="credits_updated",
        data=res.model_dump(),
        channel="general",
    )

    return res


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
    cache_key = f"usage:{org.id}:{scope}:{target_user_id or 'all'}"

    cached_data = await memory_cache.get(cache_key)
    if cached_data is not None:
        return TokenUtilizationSummary.model_validate(cached_data)

    res = await ai_credit_service.get_token_utilization_summary(db, org, user_id=target_user_id)
    await memory_cache.set(cache_key, res.model_dump(), ttl_seconds=USAGE_CACHE_TTL)
    return res


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
        db, org, target_user.id, payload.amount, reason=payload.reason
    )
    await db.commit()
    res = AICreditBalanceResponse.from_wallet(wallet)

    # Invalidate cache
    await memory_cache.delete(f"credits:{target_user.id}")
    await memory_cache.invalidate_prefix(f"usage:{org.id}")

    # Real-time WebSocket event to target user
    await ws_manager.send_to_user(
        user_id=target_user.id,
        event_type="credits_updated",
        data=res.model_dump(),
        channel="general",
    )

    return res
