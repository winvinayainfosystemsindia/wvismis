"""
AI Engine — Task Journal
=========================

Responsible for writing structured execution logs to the database
during an AI Harness task run, scoped to the user's organization.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import select, func
from app.models.ai_task_log import AITaskLog, AITaskStatus, AITaskTrigger
from app.ai.brain.schemas import ToolCallPlan, ToolStepLog, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TaskJournal:
    """Manages all DB writes for a single AI Harness task run."""

    def __init__(self, log: AITaskLog, db: "AsyncSession"):
        self._log = log
        self._db = db
        self._steps: list[ToolStepLog] = []
        self._wall_start = time.monotonic()

    @classmethod
    async def create(
        cls,
        db: "AsyncSession",
        task_name: str,
        trigger: AITaskTrigger,
        raw_input: dict[str, Any],
        ai_provider: str,
        ai_model: str,
        triggered_by_user_id: int | None = None,
        organization_id: int | None = None,
        chat_session_id: int | None = None,
    ) -> "TaskJournal":
        """Create a new task journal entry and persist it immediately."""
        log = AITaskLog(
            organization_id=organization_id,
            task_name=task_name,
            trigger=trigger,
            status=AITaskStatus.PENDING,
            raw_input=raw_input,
            ai_provider=ai_provider,
            ai_model=ai_model,
            triggered_by_user_id=triggered_by_user_id,
            chat_session_id=chat_session_id,
            steps=[],
            tools_called=0,
            tools_succeeded=0,
            tools_failed=0,
            records_affected=0,
            requires_approval=False,
        )
        db.add(log)
        await db.flush()
        logger.info("TaskJournal created: id=%d, org=%s, task='%s'", log.id, organization_id, task_name)
        return cls(log=log, db=db)

    async def mark_planning(self) -> None:
        self._log.status = AITaskStatus.PLANNING
        self._log.started_at = datetime.now(timezone.utc)
        await self._flush()

    async def mark_running(self) -> None:
        self._log.status = AITaskStatus.RUNNING
        await self._flush()

    async def mark_awaiting_approval(self, reason: str, pending_tool: str) -> None:
        self._log.status = AITaskStatus.AWAITING_APPROVAL
        self._log.requires_approval = True
        self._log.summary = f"Awaiting approval: {reason} (blocked on: {pending_tool})"
        await self._flush()

    async def record_plan(self, plan: ToolCallPlan, context_snapshot: dict | None = None) -> None:
        self._log.plan_reasoning = plan.reasoning
        self._log.plan = [step.model_dump() for step in plan.steps]
        self._log.context_snapshot = context_snapshot
        await self._flush()

    async def record_step_start(
        self,
        step_number: int,
        tool_name: str,
        parameters: dict[str, Any],
        reasoning: str | None = None,
    ) -> None:
        step = ToolStepLog(
            step_number=step_number,
            tool_name=tool_name,
            parameters=parameters,
            reasoning=reasoning,
            status="pending_approval",
            started_at=datetime.now(timezone.utc),
        )
        self._upsert_step(step)
        await self._persist_steps()

    async def record_step_result(
        self,
        step_number: int,
        result: ToolResult,
    ) -> None:
        step = self._get_step(step_number)
        if step is None:
            return

        step.status = "success" if result.success else "failed"
        step.result_data = result.data
        step.result_message = result.message
        step.records_affected = result.records_affected
        step.error = result.error
        step.completed_at = datetime.now(timezone.utc)

        if step.started_at:
            delta = (step.completed_at - step.started_at).total_seconds() * 1000
            step.duration_ms = int(delta)

        self._log.tools_called += 1
        if result.success:
            self._log.tools_succeeded += 1
        else:
            self._log.tools_failed += 1
        self._log.records_affected += result.records_affected

        self._upsert_step(step)
        await self._persist_steps()

    async def finalize(
        self,
        status: AITaskStatus,
        summary: str,
        error_message: str | None = None,
        llm_tokens_used: int | None = None,
        llm_cost_usd: float | None = None,
    ) -> None:
        self._log.status = status
        self._log.summary = summary
        self._log.error_message = error_message
        self._log.completed_at = datetime.now(timezone.utc)
        self._log.llm_tokens_used = llm_tokens_used
        self._log.llm_cost_usd = llm_cost_usd
        self._log.duration_ms = int((time.monotonic() - self._wall_start) * 1000)

        await self._persist_steps()
        await self._db.commit()

    @property
    def task_id(self) -> int:
        return self._log.id

    @property
    def public_id(self) -> uuid.UUID:
        return self._log.public_id

    @property
    def log(self) -> AITaskLog:
        return self._log

    async def _flush(self) -> None:
        await self._db.flush()

    async def _persist_steps(self) -> None:
        self._log.steps = [s.model_dump(mode="json") for s in self._steps]
        await self._flush()

    def _upsert_step(self, step: ToolStepLog) -> None:
        for i, existing in enumerate(self._steps):
            if existing.step_number == step.step_number:
                self._steps[i] = step
                return
        self._steps.append(step)
        self._steps.sort(key=lambda s: s.step_number)

    def _get_step(self, step_number: int) -> ToolStepLog | None:
        for step in self._steps:
            if step.step_number == step_number:
                return step
        return None


async def get_task_log_by_public_id(
    db: "AsyncSession",
    public_id: str,
    organization_id: Optional[int] = None,
) -> AITaskLog | None:
    try:
        parsed_uuid = uuid.UUID(str(public_id))
    except ValueError:
        return None

    stmt = select(AITaskLog).where(AITaskLog.public_id == parsed_uuid)
    if organization_id is not None:
        stmt = stmt.where(AITaskLog.organization_id == organization_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_task_logs(
    db: "AsyncSession",
    organization_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
) -> tuple[list[AITaskLog], int]:
    """Paginated task log list with tenant isolation and optional status filter."""
    query = select(AITaskLog)
    count_query = select(func.count(AITaskLog.id))

    if organization_id is not None:
        query = query.where(AITaskLog.organization_id == organization_id)
        count_query = count_query.where(AITaskLog.organization_id == organization_id)

    if status_filter:
        query = query.where(AITaskLog.status == status_filter)
        count_query = count_query.where(AITaskLog.status == status_filter)

    query = (
        query.order_by(AITaskLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items_result = await db.execute(query)
    count_result = await db.execute(count_query)

    return list(items_result.scalars().all()), count_result.scalar() or 0
