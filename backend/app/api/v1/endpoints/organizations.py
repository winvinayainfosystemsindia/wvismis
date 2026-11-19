"""Organizations (Multi-Tenancy) endpoints — Manage tenant organizations, settings, and quotas"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.core.rate_limiter import rate_limit_medium
from app.api.deps import (
    get_current_user,
    get_current_superuser,
    get_current_organization,
    require_roles,
)
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    PaginatedOrganizationResponse,
)
from app.schemas.user import PaginatedResponse
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService
from app.utils.activity_tracker import log_create, log_update, log_delete


router = APIRouter(prefix="/organizations", tags=["Multi-Tenancy (Organizations)"])


@router.get(
    "/current",
    response_model=OrganizationResponse,
    summary="Get the caller's current Organization (Tenant)",
)
@rate_limit_medium()
async def get_my_organization(
    request: Request,
    current_org: Organization = Depends(get_current_organization),
):
    """Returns full details of the active tenant organization for the current request."""
    return current_org


@router.put(
    "/current",
    response_model=OrganizationResponse,
    summary="Update current Organization settings (Org Admin / Admin)",
)
@rate_limit_medium()
async def update_my_organization(
    request: Request,
    org_in: OrganizationUpdate,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Update profile, branding, contact details, or settings for the active Organization."""
    # Prevent regular ORG_ADMIN from modifying subscription plan or max_users quota
    if not current_user.is_superuser and current_user.role != UserRole.SUPER_ADMIN:
        org_in.subscription_plan = None
        org_in.max_users = None
        org_in.is_active = None

    org_service = OrganizationService(db)
    before = current_org.dict()
    updated_org = await org_service.update_organization(current_org.id, org_in)

    await log_update(
        db=db,
        request=request,
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="organization",
        resource_id=current_org.id,
        before=before,
        after=updated_org.dict(),
    )
    return updated_org


@router.get(
    "/current/stats",
    summary="Get statistics and quota utilization for the current Organization",
)
@rate_limit_medium()
async def get_my_organization_stats(
    request: Request,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN, UserRole.MANAGER])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Returns active user count, role breakdown, and remaining tenant seat capacity."""
    total_res = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id == current_org.id,
            User.is_deleted == False,
        )
    )
    total_users = total_res.scalar() or 0

    active_res = await db.execute(
        select(func.count(User.id)).where(
            User.organization_id == current_org.id,
            User.is_deleted == False,
            User.is_active == True,
        )
    )
    active_users = active_res.scalar() or 0

    role_res = await db.execute(
        select(User.role, func.count(User.id))
        .where(
            User.organization_id == current_org.id,
            User.is_deleted == False,
        )
        .group_by(User.role)
    )
    by_role = {role.value: count for role, count in role_res.all()}

    return {
        "organization_id": current_org.id,
        "name": current_org.name,
        "slug": current_org.slug,
        "subscription_plan": current_org.subscription_plan.value,
        "max_users": current_org.max_users,
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "remaining_capacity": max(0, current_org.max_users - active_users),
        "users_by_role": by_role,
    }


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Organization tenant (Superuser only)",
)
@rate_limit_medium()
async def create_organization(
    request: Request,
    org_in: OrganizationCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Provision a new Organization tenant."""
    org_service = OrganizationService(db)
    org = await org_service.create_organization(org_in)

    await log_create(
        db=db,
        request=request,
        organization_id=org.id,
        user_id=current_user.id,
        resource_type="organization",
        resource_id=org.id,
        created_object=org,
    )
    logger.info(f"Organization created: {org.slug} (id={org.id}) by {current_user.email}")
    return org


@router.get(
    "/",
    response_model=PaginatedOrganizationResponse,
    summary="List all Organizations (Superuser sees all; tenant user sees own organization)",
)
@rate_limit_medium()
async def list_organizations(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List organizations with pagination and search."""
    org_service = OrganizationService(db)

    if not current_user.is_superuser and current_user.role != UserRole.SUPER_ADMIN:
        if not current_user.organization_id:
            return PaginatedOrganizationResponse(
                total=0,
                page=1,
                page_size=limit,
                total_pages=0,
                items=[],
            )
        org = await org_service.get_organization(current_user.organization_id)
        return PaginatedOrganizationResponse(
            total=1,
            page=1,
            page_size=limit,
            total_pages=1,
            items=[OrganizationResponse.model_validate(org)],
        )

    orgs, total = await org_service.list_organizations(
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
    )
    return PaginatedOrganizationResponse(
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
        items=[OrganizationResponse.model_validate(o) for o in orgs],
    )


@router.get(
    "/parent",
    response_model=OrganizationResponse,
    summary="Get root / parent organization (WinVinaya Infosystems)",
)
@rate_limit_medium()
async def get_parent_organization(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the root parent organization (WinVinaya Infosystems) for the MIS platform."""
    org_service = OrganizationService(db)
    parent_org = await org_service.get_or_create_default_organization()
    return parent_org


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get Organization by ID",
)
@rate_limit_medium()
async def get_organization(
    request: Request,
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific organization by ID (enforces tenant isolation for non-superusers)."""
    if (
        not current_user.is_superuser
        and current_user.role != UserRole.SUPER_ADMIN
        and current_user.organization_id != org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to another organization",
        )
    org_service = OrganizationService(db)
    return await org_service.get_organization(org_id)


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update Organization by ID",
)
@rate_limit_medium()
async def update_organization(
    request: Request,
    org_id: int,
    org_in: OrganizationUpdate,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Update an organization by ID."""
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    if not is_super and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to modify another organization",
        )

    if not is_super:
        org_in.subscription_plan = None
        org_in.max_users = None
        org_in.is_active = None

    org_service = OrganizationService(db)
    existing = await org_service.get_organization(org_id)
    before = existing.dict()
    updated = await org_service.update_organization(org_id, org_in)

    await log_update(
        db=db,
        request=request,
        organization_id=org_id,
        user_id=current_user.id,
        resource_type="organization",
        resource_id=org_id,
        before=before,
        after=updated.dict(),
    )
    return updated


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Organization by ID (Superuser only)",
)
@rate_limit_medium()
async def delete_organization(
    request: Request,
    org_id: int,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an organization tenant."""
    org_service = OrganizationService(db)
    await org_service.delete_organization(org_id)

    await log_delete(
        db=db,
        request=request,
        organization_id=org_id,
        user_id=current_user.id,
        resource_type="organization",
        resource_id=org_id,
    )
    return None


@router.get(
    "/{org_id}/users",
    response_model=PaginatedResponse,
    summary="List users belonging to an Organization",
)
@rate_limit_medium()
async def get_organization_users(
    request: Request,
    org_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    role: Optional[UserRole] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN, UserRole.MANAGER])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of users for a specific organization."""
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    if not is_super and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to another organization's users",
        )

    user_service = UserService(db)
    users = await user_service.get_users(
        skip=skip,
        limit=limit,
        organization_id=org_id,
        role=role.value if role else None,
        search=search,
    )

    total = await user_service.repository.count(organization_id=org_id)
    return PaginatedResponse(
        items=users,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
