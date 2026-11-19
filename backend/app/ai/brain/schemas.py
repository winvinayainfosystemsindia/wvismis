"""
AI Engine — Core Execution Schemas
==================================

Pydantic models for the internal execution contracts of the Harness Agentic AI engine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class ToolParameterSchema(BaseModel):
    """JSON Schema for a single tool parameter."""
    type: str
    description: str
    enum: list[str] | None = None
    default: Any = None


class ToolDefinition(BaseModel):
    """Full MCP-compatible tool definition injected into the LLM system prompt."""
    name: str = Field(..., description="Unique, snake_case tool identifier")
    description: str = Field(..., description="What this tool does (fed to the LLM)")
    category: str = Field(
        ...,
        description="Grouping: organization | users | audit | streaming | system",
    )
    requires_approval: bool = Field(
        default=False,
        description="If True, Harness pauses and asks for human approval before executing",
    )
    is_read_only: bool = Field(
        default=False,
        description="If True, this tool only reads data; never modifies the DB",
    )
    allowed_roles: list[str] = Field(
        default_factory=lambda: ["super_admin", "org_admin", "admin", "manager"],
        description="User roles permitted to invoke this tool",
    )
    parameters: dict[str, ToolParameterSchema] = Field(
        default_factory=dict,
        description="Map of parameter name -> schema",
    )
    required_parameters: list[str] = Field(
        default_factory=list,
        description="Names of parameters that MUST be supplied",
    )

    model_config = ConfigDict(from_attributes=True)


class ToolCallRequest(BaseModel):
    """A single tool call as planned by the LLM planner."""
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = Field(
        default=None,
        description="LLM's reasoning for why this tool call is needed",
    )


class ToolResult(BaseModel):
    """The return value every tool's execute() method must return."""
    success: bool
    message: str = Field(..., description="Human-readable outcome summary")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Returned structured data",
    )
    records_affected: int = Field(
        default=0,
        description="Number of DB records created, updated, or deleted",
    )
    error: str | None = None


class ToolCallPlan(BaseModel):
    """The structured output the LLM Planner produces before execution begins."""
    task_name: str
    reasoning: str = Field(..., description="Chain-of-thought explanation of the overall plan")
    response_to_user: str | None = Field(
        None,
        description="Immediate reply to show the user while tools are running",
    )
    steps: list[ToolCallRequest] = Field(..., description="Ordered list of tool calls to make")
    estimated_record_impact: int = Field(
        default=0,
        description="LLM's estimate of how many DB records this plan will touch",
    )


class ToolStepLog(BaseModel):
    """Immutable record of one tool call's execution — written to the task journal."""
    step_number: int
    tool_name: str
    parameters: dict[str, Any]
    reasoning: str | None = None
    status: Literal["success", "failed", "skipped", "pending_approval"] = "pending_approval"
    result_data: dict[str, Any] | None = None
    result_message: str | None = None
    error: str | None = None
    records_affected: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
