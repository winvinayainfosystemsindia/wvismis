"""Plan Pydantic schemas"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.plan import PlanTier


class PlanResponse(BaseModel):
    """Public-facing representation of a pricing plan, e.g. for a pricing page."""

    id: Optional[int] = None
    tier: PlanTier
    name: str
    enabled_modules: List[str]
    ai_credits_monthly: int
    user_limit: Optional[int] = None
    price_per_user: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    enabled_modules: Optional[List[str]] = None
    ai_credits_monthly: Optional[int] = None
    user_limit: Optional[int] = None
    price_per_user: Optional[int] = None
