"""Token Blacklist repository for revoking and checking JWT JTIs"""

from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.token_blacklist import TokenBlacklist
from app.repositories.base import BaseRepository


class TokenBlacklistRepository(BaseRepository[TokenBlacklist]):
    """Repository for managing revoked JWT tokens"""

    def __init__(self, db: AsyncSession):
        super().__init__(TokenBlacklist, db)

    async def is_blacklisted(self, jti: str) -> bool:
        """Check whether a JWT JTI has been revoked"""
        if not jti:
            return False
        query = select(TokenBlacklist.id).where(
            TokenBlacklist.jti == jti,
            TokenBlacklist.is_deleted == False,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def blacklist_token(
        self,
        jti: str,
        token_type: str,
        expires_at: datetime,
        user_id: Optional[int] = None,
        reason: Optional[str] = "logout",
    ) -> TokenBlacklist:
        """Add a token JTI to the blacklist if not already present"""
        existing_query = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        existing_res = await self.db.execute(existing_query)
        existing = existing_res.scalar_one_or_none()
        if existing:
            return existing

        entry = TokenBlacklist(
            jti=jti,
            token_type=token_type,
            user_id=user_id,
            expires_at=expires_at,
            reason=reason,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry
