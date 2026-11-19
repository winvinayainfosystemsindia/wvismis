"""
AI Brain — Long Term Memory & Learning
======================================

Retrieves successful past task patterns (few-shot learning) scoped to the organization
to improve the accuracy of the Harness planner.
"""

import logging
from typing import TYPE_CHECKING, Optional
from sqlalchemy import select, or_
from app.models.ai_task_log import AITaskLog, AITaskStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BrainMemory:
    """Manages historical context retrieval to provide experience to the AI Harness."""

    def __init__(self, db: "AsyncSession", organization_id: Optional[int] = None):
        self._db = db
        self._organization_id = organization_id

    async def get_similar_successful_tasks(self, task_hint: str, limit: int = 3) -> list[dict]:
        """Retrieves past successful tasks that are structurally similar within the tenant."""
        keywords = [w for w in task_hint.split() if len(w) > 4]
        if not keywords:
            return []

        conditions = [AITaskLog.task_name.ilike(f"%{kw}%") for kw in keywords[:3]]

        try:
            stmt = (
                select(AITaskLog)
                .where(or_(*conditions))
                .where(AITaskLog.status == AITaskStatus.COMPLETED)
            )
            if self._organization_id is not None:
                stmt = stmt.where(AITaskLog.organization_id == self._organization_id)

            stmt = stmt.order_by(AITaskLog.created_at.desc()).limit(limit)
            result = await self._db.execute(stmt)
            logs = result.scalars().all()

            examples = []
            for log in logs:
                if log.plan and log.summary:
                    examples.append({
                        "task": log.task_name,
                        "plan": log.plan,
                        "outcome": log.summary,
                    })
            return examples
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
            return []
