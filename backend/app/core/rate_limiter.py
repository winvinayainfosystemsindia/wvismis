"""Rate limiting configuration using SlowAPI with in-memory storage"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[
        f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
        f"{settings.RATE_LIMIT_PER_HOUR}/hour",
    ],
    enabled=settings.RATE_LIMIT_ENABLED,
    storage_uri="memory://",
)


def rate_limit_low():
    """Low rate limit for expensive operations (10/min, 100/hour)"""
    return limiter.limit("10/minute;100/hour")


def rate_limit_medium():
    """Medium rate limit for normal operations (30/min, 5000/hour)"""
    return limiter.limit("30/minute;5000/hour")


def rate_limit_high():
    """High rate limit for lightweight operations (60/min, 1000/hour)"""
    return limiter.limit("60/minute;1000/hour")


def rate_limit_auth():
    """Strict rate limit for authentication endpoints (10/min, 50/hour)"""
    return limiter.limit("10/minute;50/hour")
