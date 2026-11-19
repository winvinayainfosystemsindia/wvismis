"""Token Blacklist model for revoking JWT access and refresh tokens on logout"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class TokenBlacklist(BaseModel):
    """Stores revoked JWT token JTIs until they naturally expire"""

    __tablename__ = "token_blacklist"

    jti: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    token_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<TokenBlacklist(jti='{self.jti}', user_id={self.user_id})>"
