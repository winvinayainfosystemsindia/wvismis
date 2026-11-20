"""
Harness Agentic AI Tools — Projects & Tasks Module
==================================================

Registered MCP tools enabling ARIA to inspect, analyze, create, and manage
Projects, Tasks, Subtasks, Budgets, and Delivery Health within the organization.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, TYPE_CHECKING
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.ai.brain.schemas import ToolDefinition, ToolParameterSchema, ToolResult
from app.ai.mcp.base_tool import BaseTool
from app.ai.mcp.registry import registry
from app.models.user import User, UserRole
from app.models.project import (
    Project,
    ProjectTask,
    ProjectTaskStatus,
    ProjectStatus,
    BillingType,
    LeadPriority,
)
from app.models.timesheet import ProjectTimeLog
from app.services.project import ProjectService
from app.services.project_templates import PROJECT_TEMPLATES

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SearchProjectsTool(BaseTool):
    """Searches and lists projects within the user's organization."""

    definition = ToolDefinition(
        name="search_projects",
        description="Search or list delivery projects in the organization by name, status, phase, or owner.",
        category="projects",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "query": ToolParameterSchema(
                type="string",
                description="Search keyword matching project name, description, or phase",
            ),
            "status": ToolParameterSchema(
                type="string",
                description="Filter by project status (e.g. planning, active, in_progress, delayed, completed)",
                enum=[s.value for s in ProjectStatus],
            ),
            "owner_id": ToolParameterSchema(
                type="integer",
                description="Filter by owner user ID",
            ),
            "limit": ToolParameterSchema(
                type="integer",
                description="Max projects to return (default: 10, max: 30)",
                default=10,
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        query_str = params.get("query")
        status_str = params.get("status")
        owner_id = params.get("owner_id")
        limit = min(int(params.get("limit", 10)), 30)

        stmt = (
            select(Project)
            .options(selectinload(Project.owner))
            .where(
                Project.organization_id == user.organization_id,
                Project.is_deleted == False,
            )
        )

        if status_str:
            stmt = stmt.where(Project.status == status_str)
        if owner_id:
            stmt = stmt.where(Project.owner_id == int(owner_id))
        if query_str:
            stmt = stmt.where(
                Project.name.ilike(f"%{query_str}%")
                | Project.description.ilike(f"%{query_str}%")
                | Project.phase.ilike(f"%{query_str}%")
            )

        res = await db.execute(stmt.order_by(Project.id.desc()).limit(limit))
        projects = list(res.scalars().all())

        results = []
        for p in projects:
            # Count total and completed tasks
            task_counts_res = await db.execute(
                select(
                    func.count(ProjectTask.id),
                    func.count(ProjectTask.completed_at),
                ).where(
                    ProjectTask.project_id == p.id,
                    ProjectTask.is_deleted == False,
                )
            )
            total_tasks, completed_tasks = task_counts_res.first() or (0, 0)
            progress = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

            results.append({
                "id": p.id,
                "public_id": str(p.public_id),
                "name": p.name,
                "status": p.status.value,
                "phase": p.phase or "N/A",
                "budget": float(p.budget) if p.budget else None,
                "currency": p.currency,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "owner_name": p.owner.full_name or p.owner.username if p.owner else "Unassigned",
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "progress_percentage": progress,
            })

        return ToolResult(
            success=True,
            message=f"Found **{len(results)}** project(s) matching your criteria in the organization.",
            data={"projects": results, "count": len(results)},
        )


class GetProjectDetailsTool(BaseTool):
    """Retrieves comprehensive details, task metrics, and budget tracking for a specific project."""

    definition = ToolDefinition(
        name="get_project_details",
        description="Get deep operational details for a project including task progress, overdue tasks, and logged hours.",
        category="projects",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "project_id": ToolParameterSchema(
                type="integer",
                description="Database ID of the project",
            ),
            "project_name": ToolParameterSchema(
                type="string",
                description="Project name to search if ID is not known",
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        project_id = params.get("project_id")
        project_name = params.get("project_name")

        stmt = (
            select(Project)
            .options(
                selectinload(Project.owner),
                selectinload(Project.task_statuses),
            )
            .where(
                Project.organization_id == user.organization_id,
                Project.is_deleted == False,
            )
        )

        if project_id:
            stmt = stmt.where(Project.id == int(project_id))
        elif project_name:
            stmt = stmt.where(Project.name.ilike(f"%{project_name.strip()}%"))
        else:
            return ToolResult(success=False, message="Please specify either 'project_id' or 'project_name'.")

        res = await db.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            return ToolResult(success=False, message="Project not found in your organization.")

        # Aggregate task statistics
        tasks_res = await db.execute(
            select(ProjectTask)
            .options(
                selectinload(ProjectTask.status),
                selectinload(ProjectTask.assignee),
            )
            .where(
                ProjectTask.project_id == project.id,
                ProjectTask.is_deleted == False,
            )
        )
        tasks = list(tasks_res.scalars().all())

        today = date.today()
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.completed_at is not None or (t.status and t.status.is_done_status))
        overdue_tasks = sum(1 for t in tasks if t.due_date and t.due_date < today and not t.completed_at and not (t.status and t.status.is_done_status))

        # Timesheet actual logged hours
        hours_res = await db.execute(
            select(func.sum(ProjectTimeLog.hours)).where(
                ProjectTimeLog.project_id == project.id,
                ProjectTimeLog.organization_id == user.organization_id,
                ProjectTimeLog.is_deleted == False,
            )
        )
        total_logged_hours = float(hours_res.scalar() or 0.0)

        # Status distribution
        status_counts: dict[str, int] = {}
        for t in tasks:
            s_name = t.status.name if t.status else "Unassigned"
            status_counts[s_name] = status_counts.get(s_name, 0) + 1

        data = {
            "id": project.id,
            "public_id": str(project.public_id),
            "name": project.name,
            "description": project.description,
            "status": project.status.value,
            "phase": project.phase,
            "budget": float(project.budget) if project.budget else None,
            "currency": project.currency,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "owner": project.owner.full_name or project.owner.username if project.owner else "Unassigned",
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "completion_percentage": round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0,
            "total_logged_hours": round(total_logged_hours, 2),
            "status_breakdown": status_counts,
        }

        msg = (
            f"**{project.name}** is currently **{project.status.value.upper()}** (Phase: {project.phase or 'N/A'}).\n"
            f"- **Progress**: {data['completion_percentage']}% ({completed_tasks}/{total_tasks} tasks done)\n"
            f"- **Overdue Tasks**: {overdue_tasks}\n"
            f"- **Total Hours Logged**: {data['total_logged_hours']} hrs (Budget: {project.currency} {data['budget'] or 'Unset'})"
        )

        return ToolResult(success=True, message=msg, data=data)


class CreateProjectTool(BaseTool):
    """Creates a new delivery project and automatically configures its task workflow board."""

    definition = ToolDefinition(
        name="create_project",
        description="Create a new delivery project with start/end dates, budget, phase, and task workflow board.",
        category="projects",
        is_read_only=False,
        requires_approval=False,
        allowed_roles=["super_admin", "org_admin", "owner", "admin", "manager", "project_coordinator"],
        parameters={
            "name": ToolParameterSchema(
                type="string",
                description="Project name",
            ),
            "description": ToolParameterSchema(
                type="string",
                description="Detailed description or scope of the project",
            ),
            "start_date": ToolParameterSchema(
                type="string",
                description="Project start date in YYYY-MM-DD format",
            ),
            "end_date": ToolParameterSchema(
                type="string",
                description="Target completion date in YYYY-MM-DD format",
            ),
            "budget": ToolParameterSchema(
                type="number",
                description="Allocated budget amount",
            ),
            "currency": ToolParameterSchema(
                type="string",
                description="Currency code (e.g. USD, INR, EUR)",
                default="USD",
            ),
            "phase": ToolParameterSchema(
                type="string",
                description="Initial phase (e.g. Discovery, Development, Testing, Deployment)",
                default="Discovery",
            ),
            "template_key": ToolParameterSchema(
                type="string",
                description="Workflow template key (e.g. software_dev, consulting, marketing, blank)",
                enum=list(PROJECT_TEMPLATES.keys()) if PROJECT_TEMPLATES else ["blank"],
                default="software_dev",
            ),
        },
        required_parameters=["name"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        name = params["name"].strip()
        description = params.get("description")
        budget = float(params["budget"]) if params.get("budget") is not None else None
        currency = (params.get("currency") or "USD").upper().strip()
        phase = params.get("phase") or "Discovery"
        template_key = params.get("template_key") or "software_dev"

        start_date = None
        if params.get("start_date"):
            try:
                start_date = date.fromisoformat(params["start_date"])
            except ValueError:
                pass

        end_date = None
        if params.get("end_date"):
            try:
                end_date = date.fromisoformat(params["end_date"])
            except ValueError:
                pass

        # Check for duplicate project name
        existing_res = await db.execute(
            select(Project).where(
                Project.organization_id == user.organization_id,
                Project.name.ilike(name),
                Project.is_deleted == False,
            )
        )
        if existing_res.scalar_one_or_none():
            return ToolResult(
                success=False,
                message=f"A project named **'{name}'** already exists in your organization. Choose a distinct name or update the existing project.",
            )

        project = Project(
            organization_id=user.organization_id,
            name=name,
            description=description,
            status=ProjectStatus.ACTIVE,
            owner_id=user.id,
            start_date=start_date or date.today(),
            end_date=end_date,
            budget=budget,
            currency=currency,
            phase=phase,
            template_key=template_key,
        )
        db.add(project)
        await db.flush()

        # Seed task statuses based on template
        await ProjectService.seed_project_task_statuses(db, project, template_key)
        await db.commit()

        return ToolResult(
            success=True,
            message=f"Project **{project.name}** (ID: {project.id}) has been created successfully with template `{template_key}`.",
            data={"project_id": project.id, "public_id": str(project.public_id), "name": project.name, "status": project.status.value},
            records_affected=1,
        )


class UpdateProjectStatusTool(BaseTool):
    """Updates the status or phase of a project."""

    definition = ToolDefinition(
        name="update_project_status",
        description="Transition a project's operational status (e.g. active, in_progress, delayed, completed, on_hold).",
        category="projects",
        is_read_only=False,
        requires_approval=False,
        allowed_roles=["super_admin", "org_admin", "owner", "admin", "manager", "project_coordinator"],
        parameters={
            "project_id": ToolParameterSchema(
                type="integer",
                description="Project database ID",
            ),
            "status": ToolParameterSchema(
                type="string",
                description="New project status",
                enum=[s.value for s in ProjectStatus],
            ),
            "phase": ToolParameterSchema(
                type="string",
                description="Optional updated project phase",
            ),
        },
        required_parameters=["project_id", "status"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        project_id = int(params["project_id"])
        new_status = params["status"].lower().strip()
        phase = params.get("phase")

        res = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == user.organization_id,
                Project.is_deleted == False,
            )
        )
        project = res.scalar_one_or_none()
        if not project:
            return ToolResult(success=False, message=f"Project ID {project_id} not found in your organization.")

        old_status = project.status.value
        project.status = ProjectStatus(new_status)
        if phase:
            project.phase = phase.strip()

        await db.commit()
        return ToolResult(
            success=True,
            message=f"Project **{project.name}** status updated from `{old_status}` to **`{new_status}`**.",
            data={"project_id": project.id, "old_status": old_status, "new_status": new_status, "phase": project.phase},
            records_affected=1,
        )


class ListProjectTasksTool(BaseTool):
    """Lists and filters tasks under a project."""

    definition = ToolDefinition(
        name="list_project_tasks",
        description="List and filter tasks for a project by assignee, priority, status, or overdue status.",
        category="projects",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "project_id": ToolParameterSchema(
                type="integer",
                description="Project ID to list tasks for",
            ),
            "project_name": ToolParameterSchema(
                type="string",
                description="Project name to search if ID not known",
            ),
            "assignee_id": ToolParameterSchema(
                type="integer",
                description="Filter by assigned user ID",
            ),
            "priority": ToolParameterSchema(
                type="string",
                description="Filter by priority (low, medium, high, urgent)",
                enum=[p.value for p in LeadPriority],
            ),
            "is_overdue_only": ToolParameterSchema(
                type="boolean",
                description="If True, only returns overdue tasks",
                default=False,
            ),
            "limit": ToolParameterSchema(
                type="integer",
                description="Max tasks to return (default: 20)",
                default=20,
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        project_id = params.get("project_id")
        project_name = params.get("project_name")
        assignee_id = params.get("assignee_id")
        priority = params.get("priority")
        is_overdue = params.get("is_overdue_only", False)
        limit = min(int(params.get("limit", 20)), 50)

        # Resolve project if name provided
        if not project_id and project_name:
            p_res = await db.execute(
                select(Project.id).where(
                    Project.organization_id == user.organization_id,
                    Project.name.ilike(f"%{project_name.strip()}%"),
                    Project.is_deleted == False,
                )
            )
            p_row = p_res.first()
            if p_row:
                project_id = p_row[0]

        stmt = (
            select(ProjectTask)
            .options(
                selectinload(ProjectTask.status),
                selectinload(ProjectTask.assignee),
                selectinload(ProjectTask.project),
            )
            .where(
                ProjectTask.organization_id == user.organization_id,
                ProjectTask.is_deleted == False,
            )
        )

        if project_id:
            stmt = stmt.where(ProjectTask.project_id == int(project_id))
        if assignee_id:
            stmt = stmt.where(ProjectTask.assignee_id == int(assignee_id))
        if priority:
            stmt = stmt.where(ProjectTask.priority == priority)

        today = date.today()
        if is_overdue:
            stmt = stmt.where(
                ProjectTask.due_date < today,
                ProjectTask.completed_at.is_(None),
            )

        res = await db.execute(stmt.order_by(ProjectTask.id.desc()).limit(limit))
        tasks = list(res.scalars().all())

        items = []
        for t in tasks:
            is_done = t.completed_at is not None or (t.status and t.status.is_done_status)
            task_overdue = bool(t.due_date and t.due_date < today and not is_done)
            items.append({
                "id": t.id,
                "public_id": str(t.public_id),
                "title": t.title,
                "project_name": t.project.name if t.project else "Unknown",
                "status": t.status.name if t.status else "Unassigned",
                "priority": t.priority.value,
                "assignee": t.assignee.full_name or t.assignee.username if t.assignee else "Unassigned",
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "estimated_hours": float(t.estimated_hours) if t.estimated_hours else None,
                "is_overdue": task_overdue,
                "is_completed": is_done,
            })

        return ToolResult(
            success=True,
            message=f"Found **{len(items)}** task(s) matching your criteria.",
            data={"tasks": items, "count": len(items)},
        )


class CreateProjectTaskTool(BaseTool):
    """Creates a new task or subtask within a project."""

    definition = ToolDefinition(
        name="create_project_task",
        description="Create a new task under a project with priority, assignee, due date, and estimated hours.",
        category="projects",
        is_read_only=False,
        requires_approval=False,
        allowed_roles=[r.value for r in UserRole],
        parameters={
            "project_id": ToolParameterSchema(
                type="integer",
                description="Project database ID",
            ),
            "title": ToolParameterSchema(
                type="string",
                description="Task title",
            ),
            "description": ToolParameterSchema(
                type="string",
                description="Task description and requirements",
            ),
            "assignee_id": ToolParameterSchema(
                type="integer",
                description="ID of the user assigned to this task",
            ),
            "priority": ToolParameterSchema(
                type="string",
                description="Task priority",
                enum=[p.value for p in LeadPriority],
                default="medium",
            ),
            "due_date": ToolParameterSchema(
                type="string",
                description="Target completion date in YYYY-MM-DD format",
            ),
            "estimated_hours": ToolParameterSchema(
                type="number",
                description="Estimated hours to complete",
            ),
            "parent_task_id": ToolParameterSchema(
                type="integer",
                description="Parent task ID if this is a subtask",
            ),
        },
        required_parameters=["project_id", "title"],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        project_id = int(params["project_id"])
        title = params["title"].strip()
        description = params.get("description")
        assignee_id = int(params["assignee_id"]) if params.get("assignee_id") else None
        priority_val = params.get("priority") or "medium"
        parent_task_id = int(params["parent_task_id"]) if params.get("parent_task_id") else None
        estimated_hours = float(params["estimated_hours"]) if params.get("estimated_hours") is not None else None

        # Verify project exists in org
        p_res = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == user.organization_id,
                Project.is_deleted == False,
            )
        )
        project = p_res.scalar_one_or_none()
        if not project:
            return ToolResult(success=False, message=f"Project ID {project_id} not found in your organization.")

        # Find initial status for the project
        status_res = await db.execute(
            select(ProjectTaskStatus)
            .where(
                ProjectTaskStatus.project_id == project_id,
                ProjectTaskStatus.organization_id == user.organization_id,
                ProjectTaskStatus.is_deleted == False,
            )
            .order_by(ProjectTaskStatus.is_initial_status.desc(), ProjectTaskStatus.order.asc())
        )
        initial_status = status_res.scalar_one_or_none()
        if not initial_status:
            # Fallback seed if empty
            await ProjectService.seed_project_task_statuses(db, project, "software_dev")
            status_res2 = await db.execute(
                select(ProjectTaskStatus)
                .where(ProjectTaskStatus.project_id == project_id)
                .order_by(ProjectTaskStatus.order.asc())
            )
            initial_status = status_res2.scalars().first()

        due_date = None
        if params.get("due_date"):
            try:
                due_date = date.fromisoformat(params["due_date"])
            except ValueError:
                pass

        task = ProjectTask(
            organization_id=user.organization_id,
            project_id=project_id,
            parent_task_id=parent_task_id,
            title=title,
            description=description,
            status_id=initial_status.id,
            priority=LeadPriority(priority_val),
            assignee_id=assignee_id,
            due_date=due_date,
            estimated_hours=estimated_hours,
            billing_type=BillingType.BILLABLE,
        )
        db.add(task)
        await db.commit()

        return ToolResult(
            success=True,
            message=f"Created task **'{task.title}'** (ID: {task.id}) in project **{project.name}** with initial status `{initial_status.name}`.",
            data={"task_id": task.id, "public_id": str(task.public_id), "title": task.title, "status": initial_status.name},
            records_affected=1,
        )


class GetProjectHealthAnalysisTool(BaseTool):
    """Provides agentic AI risk and health analysis across projects."""

    definition = ToolDefinition(
        name="get_project_health_analysis",
        description="Agentic audit analyzing schedule delay risks, overdue task bottlenecks, and budget burn rates.",
        category="projects",
        is_read_only=True,
        requires_approval=False,
        allowed_roles=["super_admin", "org_admin", "owner", "admin", "manager", "project_coordinator"],
        parameters={
            "project_id": ToolParameterSchema(
                type="integer",
                description="Specific project ID to analyze, or leave empty to audit all active projects",
            ),
        },
        required_parameters=[],
    )

    async def execute(self, params: dict[str, Any], db: "AsyncSession", user: User) -> ToolResult:
        project_id = params.get("project_id")

        stmt = select(Project).where(
            Project.organization_id == user.organization_id,
            Project.is_deleted == False,
        )
        if project_id:
            stmt = stmt.where(Project.id == int(project_id))
        else:
            stmt = stmt.where(Project.status.in_([ProjectStatus.ACTIVE, ProjectStatus.IN_PROGRESS, ProjectStatus.DELAYED]))

        projects = list((await db.execute(stmt)).scalars().all())
        if not projects:
            return ToolResult(success=True, message="No active projects found to analyze.", data={"projects_analyzed": 0})

        today = date.today()
        audit_reports = []

        for p in projects:
            tasks = list((await db.execute(
                select(ProjectTask)
                .options(selectinload(ProjectTask.status), selectinload(ProjectTask.assignee))
                .where(ProjectTask.project_id == p.id, ProjectTask.is_deleted == False)
            )).scalars().all())

            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t.completed_at is not None or (t.status and t.status.is_done_status))
            overdue_tasks = [t for t in tasks if t.due_date and t.due_date < today and not t.completed_at and not (t.status and t.status.is_done_status)]

            # Logged hours
            hours_res = await db.execute(
                select(func.sum(ProjectTimeLog.hours)).where(
                    ProjectTimeLog.project_id == p.id,
                    ProjectTimeLog.organization_id == user.organization_id,
                    ProjectTimeLog.is_deleted == False,
                )
            )
            logged_hours = float(hours_res.scalar() or 0.0)

            # Risk calculation
            risk_factors = []
            if len(overdue_tasks) > 2:
                risk_factors.append(f"{len(overdue_tasks)} overdue tasks pending")
            if p.end_date and p.end_date < today and p.status != ProjectStatus.COMPLETED:
                risk_factors.append("Project past target completion date")
            if p.status == ProjectStatus.DELAYED:
                risk_factors.append("Explicitly flagged as DELAYED")

            risk_level = "High" if len(risk_factors) >= 2 else "Medium" if len(risk_factors) == 1 else "Healthy"

            audit_reports.append({
                "project_id": p.id,
                "project_name": p.name,
                "status": p.status.value,
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "overdue_count": len(overdue_tasks),
                "logged_hours": logged_hours,
                "action_recommendation": (
                    f"Reassign or unblock {len(overdue_tasks)} overdue tasks immediately."
                    if overdue_tasks
                    else "Project progress is on track."
                ),
            })

        summary_lines = []
        for r in audit_reports:
            icon = "🔴" if r["risk_level"] == "High" else "🟡" if r["risk_level"] == "Medium" else "🟢"
            summary_lines.append(
                f"{icon} **{r['project_name']}** — Risk: **{r['risk_level']}** ({r['completed_tasks']}/{r['total_tasks']} tasks done, {r['logged_hours']}h logged). "
                f"Recommendation: {r['action_recommendation']}"
            )

        return ToolResult(
            success=True,
            message="\n\n".join(summary_lines),
            data={"reports": audit_reports, "total_analyzed": len(audit_reports)},
        )


def register_project_tools() -> None:
    """Register all project and task tools in the central MCP registry."""
    registry.register(SearchProjectsTool())
    registry.register(GetProjectDetailsTool())
    registry.register(CreateProjectTool())
    registry.register(UpdateProjectStatusTool())
    registry.register(ListProjectTasksTool())
    registry.register(CreateProjectTaskTool())
    registry.register(GetProjectHealthAnalysisTool())


register_project_tools()
