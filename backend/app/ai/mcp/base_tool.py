"""
AI Engine — Base Tool Class
===========================

The foundation for all Harness Agentic AI actions.
Tools subclass BaseTool and are registered in ToolRegistry.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING
from app.ai.brain.schemas import ToolDefinition, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import User


class BaseTool:
    """Abstract base class for Harness AI tools."""

    definition: ToolDefinition

    async def execute(
        self,
        params: dict[str, Any],
        db: "AsyncSession",
        user: "User",
    ) -> ToolResult:
        """Execute this tool within the user's multi-tenant context."""
        raise NotImplementedError(f"Tool '{self.definition.name}' must implement execute()")

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters against the ToolDefinition schema."""
        errors = []
        for required in self.definition.required_parameters:
            if required not in params or params[required] is None:
                errors.append(f"Missing required parameter: '{required}'")

        for param_name, param_schema in self.definition.parameters.items():
            if (
                param_name in params
                and param_schema.enum
                and params[param_name] not in param_schema.enum
            ):
                errors.append(
                    f"Parameter '{param_name}' must be one of: {param_schema.enum}. Got: '{params[param_name]}'"
                )

        return errors
