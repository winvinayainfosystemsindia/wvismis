"""AI credit repository — wallet lookup/rollover and the atomic deduct/grant ledger writes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.ai_credit import AICreditWallet, AICreditTransaction, AICreditTransactionReason
from app.schemas.ai_credit import (
    TokenUtilizationSummary,
    AIProviderBreakdown,
    AIModelBreakdown,
    AIActionTypeBreakdown,
    AIDailyUsagePoint,
)


def current_period_start(now: datetime) -> datetime:
    """First moment of the current calendar month (UTC)."""
    return now.replace(year=now.year, month=now.month, day=1, hour=0, minute=0, second=0, microsecond=0)


class AICreditRepository:
    @staticmethod
    async def get_wallet(db: AsyncSession, organization_id: int, user_id: int) -> Optional[AICreditWallet]:
        result = await db.execute(
            select(AICreditWallet).where(
                AICreditWallet.organization_id == organization_id,
                AICreditWallet.user_id == user_id,
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_or_create_wallet(
        db: AsyncSession, organization_id: int, user_id: int, ai_credits_monthly: int = 500
    ) -> AICreditWallet:
        """Fetch this user's wallet, creating it (or rolling it to a fresh period) as needed."""
        wallet = await AICreditRepository.get_wallet(db, organization_id, user_id)
        period_start = current_period_start(datetime.now(timezone.utc))

        if wallet is None:
            wallet = AICreditWallet(
                organization_id=organization_id,
                user_id=user_id,
                period_start=period_start,
                balance=ai_credits_monthly,
                granted=ai_credits_monthly,
            )
            db.add(wallet)
            await db.flush()
            await AICreditRepository.record_grant(
                db,
                wallet,
                amount=ai_credits_monthly,
                reason=AICreditTransactionReason.MONTHLY_GRANT,
                user_id=user_id,
            )
            return wallet

        if wallet.period_start < period_start:
            wallet.period_start = period_start
            wallet.balance = ai_credits_monthly
            wallet.granted = ai_credits_monthly
            await db.flush()
            await AICreditRepository.record_grant(
                db,
                wallet,
                amount=ai_credits_monthly,
                reason=AICreditTransactionReason.MONTHLY_GRANT,
                user_id=user_id,
            )

        return wallet

    @staticmethod
    async def record_grant(
        db: AsyncSession,
        wallet: AICreditWallet,
        *,
        amount: int,
        reason: AICreditTransactionReason,
        user_id: Optional[int] = None,
    ) -> AICreditTransaction:
        txn = AICreditTransaction(
            organization_id=wallet.organization_id,
            wallet_id=wallet.id,
            user_id=user_id,
            amount=amount,
            balance_after=wallet.balance,
            reason=reason,
        )
        db.add(txn)
        await db.flush()
        return txn

    @staticmethod
    async def deduct(
        db: AsyncSession,
        wallet: AICreditWallet,
        *,
        cost: int,
        provider: str = "openai",
        model: Optional[str] = None,
        action_type: Optional[str] = None,
        user_id: Optional[int] = None,
        tokens_used: Optional[int] = None,
        is_estimated: bool = False,
    ) -> AICreditTransaction:
        """Atomically deduct `cost` credits and record the ledger row."""
        result = await db.execute(
            update(AICreditWallet)
            .where(AICreditWallet.id == wallet.id)
            .values(balance=AICreditWallet.balance - cost)
            .returning(AICreditWallet.balance)
        )
        new_balance = result.scalar_one()
        wallet.balance = new_balance

        txn = AICreditTransaction(
            organization_id=wallet.organization_id,
            wallet_id=wallet.id,
            user_id=user_id,
            amount=-cost,
            balance_after=new_balance,
            reason=AICreditTransactionReason.AI_CALL,
            provider=provider,
            model=model,
            action_type=action_type,
            tokens_used=tokens_used,
            is_estimated=is_estimated,
        )
        db.add(txn)
        await db.flush()
        return txn

    @staticmethod
    async def grant_bonus_credits(
        db: AsyncSession,
        wallet: AICreditWallet,
        *,
        amount: int,
        user_id: Optional[int],
        reason: AICreditTransactionReason,
    ) -> AICreditTransaction:
        """Adds credits to a wallet -- self-service purchase or superuser manual grant."""
        result = await db.execute(
            update(AICreditWallet)
            .where(AICreditWallet.id == wallet.id)
            .values(
                balance=AICreditWallet.balance + amount,
                granted=AICreditWallet.granted + amount,
            )
            .returning(AICreditWallet.balance, AICreditWallet.granted)
        )
        new_balance, new_granted = result.one()
        wallet.balance = new_balance
        wallet.granted = new_granted

        txn = AICreditTransaction(
            organization_id=wallet.organization_id,
            wallet_id=wallet.id,
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            reason=reason,
        )
        db.add(txn)
        await db.flush()
        return txn

    @staticmethod
    async def get_token_utilization(
        db: AsyncSession,
        organization_id: int,
        user_id: Optional[int] = None,
        period_start: Optional[datetime] = None,
    ) -> TokenUtilizationSummary:
        """Aggregate token utilization summary for a user or entire organization."""
        if period_start is None:
            period_start = current_period_start(datetime.now(timezone.utc))

        query = select(AICreditTransaction).where(
            AICreditTransaction.organization_id == organization_id,
            AICreditTransaction.reason == AICreditTransactionReason.AI_CALL,
            AICreditTransaction.created_at >= period_start,
        )
        if user_id is not None:
            query = query.where(AICreditTransaction.user_id == user_id)

        result = await db.execute(query)
        txns = list(result.scalars().all())

        total_tokens = sum(t.tokens_used or 0 for t in txns)
        total_credits = sum(abs(t.amount) for t in txns)
        total_calls = len(txns)

        # Provider breakdown
        providers: dict[str, dict] = {}
        models: dict[str, dict] = {}
        action_types: dict[str, dict] = {}
        daily_trends: dict[str, dict] = {}

        for t in txns:
            p_name = t.provider or "default"
            if p_name not in providers:
                providers[p_name] = {"tokens": 0, "credits": 0, "calls": 0}
            providers[p_name]["tokens"] += t.tokens_used or 0
            providers[p_name]["credits"] += abs(t.amount)
            providers[p_name]["calls"] += 1

            m_name = t.model or "default"
            if m_name not in models:
                models[m_name] = {"tokens": 0, "credits": 0, "calls": 0}
            models[m_name]["tokens"] += t.tokens_used or 0
            models[m_name]["credits"] += abs(t.amount)
            models[m_name]["calls"] += 1

            act = t.action_type or "general_ai"
            if act not in action_types:
                action_types[act] = {"tokens": 0, "credits": 0, "calls": 0}
            action_types[act]["tokens"] += t.tokens_used or 0
            action_types[act]["credits"] += abs(t.amount)
            action_types[act]["calls"] += 1

            day_str = t.created_at.strftime("%Y-%m-%d") if t.created_at else "today"
            if day_str not in daily_trends:
                daily_trends[day_str] = {"tokens": 0, "credits": 0, "calls": 0}
            daily_trends[day_str]["tokens"] += t.tokens_used or 0
            daily_trends[day_str]["credits"] += abs(t.amount)
            daily_trends[day_str]["calls"] += 1

        return TokenUtilizationSummary(
            total_tokens_used=total_tokens,
            total_credits_consumed=total_credits,
            total_calls=total_calls,
            by_provider=[
                AIProviderBreakdown(provider=k, **v) for k, v in providers.items()
            ],
            by_model=[
                AIModelBreakdown(model=k, **v) for k, v in models.items()
            ],
            by_action_type=[
                AIActionTypeBreakdown(action_type=k, **v) for k, v in action_types.items()
            ],
            daily_trend=[
                AIDailyUsagePoint(date=k, **v) for k, v in sorted(daily_trends.items())
            ],
        )
