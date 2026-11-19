"""AI Chat models — persists multi-turn conversation history for the Harness Agentic AI."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Literal
from sqlalchemy import String, Text, Integer, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ai_task_log import AITaskLog


class AIChatSession(BaseModel, TenantMixin):
    """Groups individual messages into a tenant-scoped conversation context."""

    __tablename__ = "ai_chat_sessions"

    public_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        unique=True,
        index=True,
        nullable=False,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New AI Harness Chat",
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    user: Mapped[User] = relationship("User", backref="chat_sessions")
    messages: Mapped[list[AIChatMessage]] = relationship(
        "AIChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AIChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<AIChatSession(id={self.id}, title='{self.title}', user_id={self.user_id})>"


class AIChatMessage(BaseModel):
    """A single message in the AI chat conversation, linked to AITaskLog when tools are invoked."""

    __tablename__ = "ai_chat_messages"

    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[Literal["user", "assistant", "system"]] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    task_log_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_task_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    session: Mapped[AIChatSession] = relationship("AIChatSession", back_populates="messages")
    task_log: Mapped[AITaskLog | None] = relationship("AITaskLog", foreign_keys=[task_log_id])

    def __repr__(self) -> str:
        return f"<AIChatMessage(id={self.id}, session_id={self.session_id}, role={self.role})>"
