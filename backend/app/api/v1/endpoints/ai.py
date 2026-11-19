"""
Harness Agentic AI Engine — REST API Endpoints
==============================================

Endpoints:
  POST  /api/v1/ai/run                  -> Trigger a Harness agentic task run
  GET   /api/v1/ai/tasks                -> List tenant-scoped task journal (paginated)
  GET   /api/v1/ai/tasks/{task_id}      -> Full task journal detail
  POST  /api/v1/ai/tasks/{task_id}/approve -> Approve a paused task
  GET   /api/v1/ai/tools                -> List all registered MCP tools
  POST  /api/v1/ai/tools/{tool_name}/execute -> Direct tool execution inside the Harness
  GET   /api/v1/ai/health               -> AI Harness engine & provider health check
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.ai.brain.engine import AIEngine
from app.ai.brain.journal import get_task_log_by_public_id, list_task_logs
from app.ai.mcp.registry import registry
from app.ai.schemas import (
    AITaskRunRequest,
    AITaskRunResponse,
    AITaskLogRead,
    AITaskLogListItem,
    ToolDefinition,
    ToolResult,
)
from app.core.config import settings
from app.models.ai_task_log import AITaskStatus
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/run",
    response_model=AITaskRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a Harness Agentic AI task run",
    description=(
        "Run an agentic AI task inside the WVISMIS Harness. The engine plans a sequence of tool calls, "
        "validates parameters, checks human-in-the-loop approval gates, executes tools within the user's "
        "Organization tenant, streams live events over WebSockets, and records an immutable task journal."
    ),
)
async def run_task(
    request: AITaskRunRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> AITaskRunResponse:
    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI Engine is currently disabled. Set AI_ENABLED=true in configuration.",
        )

    engine = AIEngine(db=db, user=current_user)
    result = await engine.run(request)

    logger.info(
        "AI task run completed: task_id=%s, status=%s, user=%d, org=%s",
        result.task_id,
        result.status,
        current_user.id,
        current_user.organization_id,
    )
    return result


@router.get(
    "/tasks",
    response_model=dict,
    summary="List Harness AI task journal (scoped to Organization)",
)
async def list_tasks(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[str | None, Query(description="Filter by status")] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_user.organization_id

    items, total = await list_task_logs(
        db=db,
        organization_id=org_filter,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
    )
    return {
        "items": [AITaskLogListItem.model_validate(item).model_dump() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.get(
    "/tasks/{task_id}",
    response_model=AITaskLogRead,
    summary="Get full Harness task journal detail",
)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> AITaskLogRead:
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_user.organization_id

    log = await get_task_log_by_public_id(db, task_id, organization_id=org_filter)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )
    return AITaskLogRead.model_validate(log)


@router.post(
    "/tasks/{task_id}/approve",
    summary="Approve a paused AI Harness task",
    status_code=status.HTTP_202_ACCEPTED,
)
async def approve_task(
    task_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(
        deps.require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN, UserRole.MANAGER])
    ),
) -> dict:
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_user.organization_id

    log = await get_task_log_by_public_id(db, task_id, organization_id=org_filter)
    if not log:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    if log.status != AITaskStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not awaiting approval. Current status: {log.status.value}",
        )

    log.approved_by_user_id = current_user.id
    log.approved_at = datetime.now(timezone.utc)
    log.status = AITaskStatus.PENDING
    await db.commit()

    return {
        "message": f"Task '{task_id}' approved. Re-trigger via POST /api/v1/ai/run to resume.",
        "approved_by": current_user.username,
    }


@router.get(
    "/tools",
    response_model=list[ToolDefinition],
    summary="List all registered Harness Agentic AI tools",
)
async def list_tools(
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    current_user: User = Depends(deps.get_current_active_user),
) -> list[ToolDefinition]:
    tools = registry.by_category(category) if category else registry.all()
    return [t.definition for t in tools]


@router.post(
    "/tools/{tool_name}/execute",
    response_model=ToolResult,
    summary="Directly invoke a registered Harness tool within tenant scope",
)
async def execute_tool_directly(
    tool_name: str,
    parameters: dict[str, Any] | None = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> ToolResult:
    """
    Execute a registered Harness tool directly with parameter validation and multi-tenant context.
    Useful for deterministic tool testing and administrative actions without requiring an LLM call.
    """
    params = parameters or {}
    try:
        tool = registry.get(tool_name)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' is not registered in the Harness ToolRegistry.",
        )

    errors = tool.validate_params(params)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="; ".join(errors),
        )

    return await tool.execute(params=params, db=db, user=current_user)


@router.get(
    "/health",
    summary="Harness Agentic AI Engine health check",
)
async def ai_health(
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    from app.ai.providers import get_provider_info, SUPPORTED_PROVIDERS

    return {
        "architecture": "Harness Agentic AI",
        "enabled": settings.AI_ENABLED,
        "active_provider": settings.AI_PROVIDER,
        "registered_tools": registry.count(),
        "tool_categories": sorted({t.definition.category for t in registry.all()}),
        "max_tool_calls_per_run": settings.AI_MAX_TOOL_CALLS_PER_RUN,
        "task_timeout_seconds": settings.AI_TASK_TIMEOUT_SECONDS,
        "approval_record_threshold": settings.AI_APPROVAL_RECORD_THRESHOLD,
        "supported_providers": SUPPORTED_PROVIDERS,
        "providers": get_provider_info(),
    }
