"""AI Task Log model — persists every Harness Agentic AI task run as an auditable journal."""

from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, JSON, Integer, Float, ForeignKey, Enum, Uuid, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ai_chat import AIChatSession


class AITaskStatus(str, enum.Enum):
    """Status of an AI Harness task execution run."""
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AITaskTrigger(str, enum.Enum):
    """What initiated this AI task."""
    MANUAL = "manual"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    API = "api"
    WEBSOCKET = "websocket"
    SYSTEM = "system"


class AITaskLog(BaseModel, TenantMixin):
    """
    Persistent task journal for every Harness Agentic AI engine run.
    Scoped to organization_id for multi-tenant isolation and auditing.
    """

    __tablename__ = "ai_task_logs"

    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        unique=True,
        index=True,
        nullable=False,
        default=uuid.uuid4,
    )

    task_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    trigger: Mapped[AITaskTrigger] = mapped_column(
        Enum(AITaskTrigger, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=AITaskTrigger.MANUAL,
    )

    status: Mapped[AITaskStatus] = mapped_column(
        Enum(AITaskStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=AITaskStatus.PENDING,
    )

    triggered_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    chat_session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    ai_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    raw_input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    plan_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tools_called: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tools_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tools_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_affected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    requires_approval: Mapped[bool] = mapped_column(default=False, nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    triggered_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[triggered_by_user_id],
        lazy="selectin",
    )

    approved_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[approved_by_user_id],
        lazy="selectin",
    )

    chat_session: Mapped[AIChatSession | None] = relationship(
        "AIChatSession",
        foreign_keys=[chat_session_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AITaskLog(id={self.id}, org_id={self.organization_id}, "
            f"task='{self.task_name}', status={self.status})>"
        )
