"""AI credit wallet and usage response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from app.models.ai_credit import AICreditWallet


class AICreditPurchaseRequest(BaseModel):
    amount: int = Field(..., gt=0, le=100_000, description="Credits to add to my own wallet")


class AICreditGrantRequest(BaseModel):
    amount: int = Field(..., gt=0, le=1_000_000, description="Credits to grant to the target user")


class AICreditBalanceResponse(BaseModel):
    balance: int
    granted: int
    period_start: datetime
    percent_used: float

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_wallet(cls, wallet: "AICreditWallet") -> "AICreditBalanceResponse":
        used = max(wallet.granted - wallet.balance, 0)
        percent_used = round((used / wallet.granted) * 100, 1) if wallet.granted else 0.0
        return cls(
            balance=wallet.balance,
            granted=wallet.granted,
            period_start=wallet.period_start,
            percent_used=percent_used,
        )


class AIUsageBreakdown(BaseModel):
    tokens: int
    credits: int
    calls: int


class AIActionTypeBreakdown(AIUsageBreakdown):
    action_type: str


class AIProviderBreakdown(AIUsageBreakdown):
    provider: str


class AIModelBreakdown(AIUsageBreakdown):
    model: str


class AIDailyUsagePoint(AIUsageBreakdown):
    date: str


class TokenUtilizationSummary(BaseModel):
    total_tokens_used: int
    total_credits_consumed: int
    total_calls: int
    by_provider: List[AIProviderBreakdown] = Field(default_factory=list)
    by_model: List[AIModelBreakdown] = Field(default_factory=list)
    by_action_type: List[AIActionTypeBreakdown] = Field(default_factory=list)
    daily_trend: List[AIDailyUsagePoint] = Field(default_factory=list)
