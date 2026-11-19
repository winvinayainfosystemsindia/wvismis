"""AI credits — per-user wallet balance plus an append-only transaction ledger.

Wallets are scoped to (organization, user) -- each user gets their own monthly allotment off
their org's plan rate, not a shared org-wide pool.
"""

from __future__ import annotations

import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class AICreditTransactionReason(str, enum.Enum):
    MONTHLY_GRANT = "monthly_grant"
    AI_CALL = "ai_call"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    PURCHASE = "purchase"


class AICreditWallet(BaseModel):
    """One row per (organization, user) — the current credit balance for the active billing period."""

    __tablename__ = "ai_credit_wallets"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_ai_credit_wallet_org_user"),
    )

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    granted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<AICreditWallet(org_id={self.organization_id}, user_id={self.user_id}, balance={self.balance}/{self.granted})>"


class AICreditTransaction(BaseModel):
    """Append-only ledger row for every credit grant or consumption event."""

    __tablename__ = "ai_credit_transactions"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    wallet_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_credit_wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who triggered this call (null for system-generated grants)",
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Negative for consumption, positive for grants/admin credits",
    )

    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    reason: Mapped[AICreditTransactionReason] = mapped_column(
        Enum(AICreditTransactionReason, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="e.g. 'chat_message', 'document_summary', 'agent_task'",
    )
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_estimated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True when tokens_used is a character-count estimate",
    )

    def __repr__(self) -> str:
        return f"<AICreditTransaction(org_id={self.organization_id}, amount={self.amount}, reason={self.reason})>"
