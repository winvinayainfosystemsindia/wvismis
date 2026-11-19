"""
AI Engine — API Request Schemas
===============================
"""

from typing import Any
from pydantic import BaseModel, Field


class AITaskRunRequest(BaseModel):
    """
    Request body for POST /api/v1/ai/run
    Supports manual, webhook, schedule, and WebSocket-triggered Harness task runs.
    """
    trigger_type: str = Field(
        default="manual",
        description="Type of trigger: manual | webhook | schedule | api | websocket",
        examples=["manual", "api"],
    )
    task_hint: str = Field(
        ...,
        description="Short description/intent of what the AI Harness should accomplish",
        examples=[
            "Show me our organization overview and user role breakdown",
            "List all active users in the organization",
        ],
    )
    input_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured input payload for the task",
    )
    context_keys: list[str] = Field(
        default_factory=list,
        description="Hints for which context to pre-load",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, plan is produced and journaled but no tools are executed",
    )
