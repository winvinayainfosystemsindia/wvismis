"""User endpoints — Multi-tenant scoped user administration and self-service profile endpoints"""

from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query, Request
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.core.rate_limiter import rate_limit_medium
from app.api.deps import get_current_user, get_current_organization, require_roles
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.schemas.user import UserResponse, UserUpdate, UserCreate, PaginatedResponse
from app.services.user_service import UserService
from app.utils.activity_tracker import log_update, log_delete, log_create


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse, summary="Get current user information")
@rate_limit_medium()
async def get_current_user_info(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user information including Organization context."""
    return current_user


@router.get("/roles", response_model=List[str], summary="Get all available user roles")
async def get_roles(
    current_user: User = Depends(get_current_user),
):
    """Return list of all user roles in WVISMIS."""
    return [role.value for role in UserRole]


@router.put("/me", response_model=UserResponse, summary="Update current user profile")
@rate_limit_medium()
async def update_current_user(
    request: Request,
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's own profile information."""
    logger.info(f"User self-update request: {current_user.email}")

    # Prevent non-admin users from escalating their own role or changing organization
    if not current_user.is_superuser and current_user.role not in (
        UserRole.SUPER_ADMIN,
        UserRole.ORG_ADMIN,
        UserRole.ADMIN,
    ):
        user_in.role = None
        user_in.organization_id = None
        user_in.is_active = None
        user_in.is_verified = None

    before_state = {
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "role": current_user.role.value,
        "department": current_user.department,
        "designation": current_user.designation,
    }

    user_service = UserService(db)
    updated_user = await user_service.update_user(current_user.id, user_in)

    after_state = {
        "email": updated_user.email,
        "username": updated_user.username,
        "full_name": updated_user.full_name,
        "is_active": updated_user.is_active,
        "role": updated_user.role.value,
        "department": updated_user.department,
        "designation": updated_user.designation,
    }
    await log_update(
        db=db,
        request=request,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        before=before_state,
        after=after_state,
    )

    return updated_user


@router.get("/stats", summary="Get user statistics for the current Organization")
@rate_limit_medium()
async def get_user_stats(
    request: Request,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN, UserRole.MANAGER])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Get user statistics scoped to the active Organization."""
    user_service = UserService(db)
    total = await user_service.repository.count(organization_id=current_org.id)

    active_query = select(func.count(User.id)).where(
        User.organization_id == current_org.id,
        User.is_deleted == False,
        User.is_active == True,
    )
    active_result = await db.execute(active_query)
    active = active_result.scalar() or 0

    role_query = (
        select(User.role, func.count(User.id))
        .where(
            User.organization_id == current_org.id,
            User.is_deleted == False,
        )
        .group_by(User.role)
    )
    role_result = await db.execute(role_query)
    role_counts = {role.value: count for role, count in role_result.all()}

    return {
        "organization_id": current_org.id,
        "organization_name": current_org.name,
        "total": total,
        "by_role": role_counts,
        "active": active,
        "inactive": total - active,
        "roles_count": len(role_counts),
    }


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user in the current Organization (Admin / Org Admin)",
)
@rate_limit_medium()
async def create_user(
    request: Request,
    user_in: UserCreate,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user inside the active Organization."""
    logger.info(
        f"Creating new user: {user_in.email} in org {current_org.slug} by {current_user.email}"
    )

    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    target_org_id = user_in.organization_id if (is_super and user_in.organization_id) else current_org.id

    user_service = UserService(db)
    user = await user_service.create_user(user_in, forced_organization_id=target_org_id)

    await log_create(
        db=db,
        request=request,
        organization_id=user.organization_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        created_object=user,
    )

    return user


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="Get paginated list of users in the current Organization",
)
@rate_limit_medium()
async def get_users(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Maximum number of records to return"),
    page: Optional[int] = Query(None, ge=1, description="Optional 1-indexed page number"),
    page_size: Optional[int] = Query(None, ge=1, le=2000, description="Optional page size"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    search: Optional[str] = Query(
        None,
        description="Search users by name, email, username, phone, or department",
    ),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Get list of users scoped to the active Organization with pagination and search."""
    effective_limit = page_size if page_size is not None else limit
    effective_skip = ((page - 1) * effective_limit) if page is not None else skip

    user_service = UserService(db)
    users = await user_service.get_users(
        skip=effective_skip,
        limit=effective_limit,
        organization_id=current_org.id,
        role=role.value if role else None,
        search=search,
    )

    filters = [User.organization_id == current_org.id]
    if role:
        filters.append(User.role == role)
    if search:
        search_filter = (
            User.full_name.ilike(f"%{search}%")
            | User.email.ilike(f"%{search}%")
            | User.username.ilike(f"%{search}%")
            | User.mobile.ilike(f"%{search}%")
            | User.department.ilike(f"%{search}%")
        )
        filters.append(search_filter)

    filter_expr = and_(*filters)
    total = await user_service.repository.count(filter_expr=filter_expr)

    return PaginatedResponse(
        items=users,
        total=total,
        page=(effective_skip // effective_limit) + 1,
        page_size=effective_limit,
        total_pages=(total + effective_limit - 1) // effective_limit if total > 0 else 0,
    )


@router.get("/search", response_model=PaginatedResponse, summary="Search users in Organization")
@rate_limit_medium()
async def search_users(
    request: Request,
    q: str = Query(..., description="Search query string"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Search users by name, email, or username within the active Organization."""
    user_service = UserService(db)
    users = await user_service.get_users(
        skip=skip,
        limit=limit,
        organization_id=current_org.id,
        search=q,
    )
    total = await user_service.repository.count(
        organization_id=current_org.id,
        filter_expr=(
            User.full_name.ilike(f"%{q}%")
            | User.email.ilike(f"%{q}%")
            | User.username.ilike(f"%{q}%")
        ),
    )
    return PaginatedResponse(
        items=users,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


async def _resolve_user_by_ref(
    db: AsyncSession,
    user_ref: str,
    organization_id: Optional[int] = None,
) -> User:
    """Resolve user by integer ID or UUID public_id"""
    import uuid as uuid_lib
    user_service = UserService(db)
    if user_ref.isdigit():
        return await user_service.get_user(int(user_ref), organization_id=organization_id)
    try:
        parsed_uuid = uuid_lib.UUID(user_ref)
        user = await user_service.repository.get_by_public_id(parsed_uuid)
    except ValueError:
        user = None
    if not user or (organization_id is not None and user.organization_id != organization_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post(
    "/invite",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new teammate into the current Organization",
)
@rate_limit_medium()
async def invite_user(
    request: Request,
    payload: dict,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user into the active Organization."""
    role_str = payload.get("role", "user")
    try:
        role_enum = UserRole(role_str)
    except ValueError:
        role_enum = UserRole.USER

    user_in = UserCreate(
        email=payload["email"],
        username=payload["username"],
        full_name=payload.get("full_name"),
        password=payload.get("password") or "Welcome@123",
        role=role_enum,
        is_active=True,
        is_verified=False,
    )
    user_service = UserService(db)
    user = await user_service.create_user(user_in, forced_organization_id=current_org.id)
    return user


@router.post("/bulk-delete", summary="Bulk soft-delete users by public_ids")
@rate_limit_medium()
async def bulk_delete_users(
    request: Request,
    payload: dict,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Bulk delete users in the active Organization."""
    public_ids = payload.get("public_ids") or []
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id
    user_service = UserService(db)
    deleted_count = 0
    for pid in public_ids:
        try:
            u = await _resolve_user_by_ref(db, str(pid), organization_id=org_filter)
            if u.id != current_user.id:
                await user_service.delete_user(u.id, organization_id=org_filter)
                deleted_count += 1
        except Exception:
            continue
    return {"message": f"Deleted {deleted_count} user(s)", "deleted_count": deleted_count}


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by ID or public_id")
@rate_limit_medium()
async def get_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN, UserRole.MANAGER])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID or public_id within the current Organization."""
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id
    return await _resolve_user_by_ref(db, user_id, organization_id=org_filter)


@router.put("/{user_id}", response_model=UserResponse, summary="Update user by ID or public_id")
@rate_limit_medium()
async def update_user(
    request: Request,
    user_id: str,
    user_in: UserUpdate,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Update user by ID or public_id within the current Organization."""
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id

    if not is_super:
        user_in.organization_id = None

    existing_user = await _resolve_user_by_ref(db, user_id, organization_id=org_filter)
    before_state = {
        "email": existing_user.email,
        "username": existing_user.username,
        "full_name": existing_user.full_name,
        "is_active": existing_user.is_active,
        "is_verified": existing_user.is_verified,
        "role": existing_user.role.value,
    }

    user_service = UserService(db)
    updated_user = await user_service.update_user(
        existing_user.id,
        user_in,
        organization_id=org_filter,
    )

    after_state = {
        "email": updated_user.email,
        "username": updated_user.username,
        "full_name": updated_user.full_name,
        "is_active": updated_user.is_active,
        "is_verified": updated_user.is_verified,
        "role": updated_user.role.value,
    }
    await log_update(
        db=db,
        request=request,
        organization_id=updated_user.organization_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=existing_user.id,
        before=before_state,
        after=after_state,
    )

    return updated_user


@router.post("/{user_id}/deactivate", response_model=UserResponse, summary="Deactivate user")
@rate_limit_medium()
async def deactivate_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id
    target = await _resolve_user_by_ref(db, user_id, organization_id=org_filter)
    user_service = UserService(db)
    return await user_service.update_user(target.id, UserUpdate(is_active=False), organization_id=org_filter)


@router.post("/{user_id}/reactivate", response_model=UserResponse, summary="Reactivate user")
@rate_limit_medium()
async def reactivate_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id
    target = await _resolve_user_by_ref(db, user_id, organization_id=org_filter)
    user_service = UserService(db)
    return await user_service.update_user(target.id, UserUpdate(is_active=True), organization_id=org_filter)


@router.post("/{user_id}/resend-invite", response_model=UserResponse, summary="Resend user invite")
@rate_limit_medium()
async def resend_user_invite(
    request: Request,
    user_id: str,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id
    return await _resolve_user_by_ref(db, user_id, organization_id=org_filter)


@router.post("/{user_id}/reset-password", response_model=UserResponse, summary="Trigger password reset")
@rate_limit_medium()
async def trigger_user_password_reset(
    request: Request,
    user_id: str,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id
    return await _resolve_user_by_ref(db, user_id, organization_id=org_filter)


@router.delete(
    "/{user_id}",
    response_model=UserResponse,
    summary="Delete user by ID or public_id (soft delete)",
)
@rate_limit_medium()
async def delete_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete user by ID or public_id within the current Organization."""
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN
    org_filter = None if is_super else current_org.id

    target = await _resolve_user_by_ref(db, user_id, organization_id=org_filter)
    user_service = UserService(db)
    await user_service.delete_user(target.id, organization_id=org_filter)

    await log_delete(
        db=db,
        request=request,
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=target.id,
    )

    return target


# ── Organization Subscription & Conversion Endpoints ─────────────────────────

from pydantic import BaseModel as _PydanticBaseModel

class ConvertToOrganizationRequest(_PydanticBaseModel):
    name: str
    location: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None


@router.post(
    "/organization/convert-to-team",
    summary="Convert your individual account into a team organization",
)
async def convert_to_team_endpoint(
    payload: ConvertToOrganizationRequest,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm.attributes import flag_modified
    current_org.name = payload.name.strip()
    if payload.location:
        current_org.address = payload.location
    if not current_org.others:
        current_org.others = {}
    current_org.others["account_type"] = "organization"
    if payload.industry:
        current_org.others["industry"] = payload.industry
    if payload.company_size:
        current_org.others["company_size"] = payload.company_size
    if payload.website:
        current_org.others["website"] = payload.website
    flag_modified(current_org, "others")

    await db.commit()
    await db.refresh(current_org)
    return {
        "success": True,
        "message": f"Your account has been converted to the '{current_org.name}' team organization.",
        "organization": {
            "name": current_org.name,
            "location": current_org.address,
            "others": current_org.others,
        },
    }


@router.put(
    "/organization/plan",
    summary="Update organization subscription plan (Org Admin)",
)
async def update_organization_plan_endpoint(
    plan_tier: str,
    account_type: Optional[str] = None,
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.plan import PlanTier, Plan
    from app.repositories.plan_repository import PlanRepository

    tier_clean = plan_tier.lower().strip()
    try:
        tier_enum = PlanTier(tier_clean)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan tier '{plan_tier}'. Available tiers: {[e.value for e in PlanTier]}",
        )

    plan = await PlanRepository.get_by_tier(db, tier_enum)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan tier '{plan_tier}' not found in database.",
        )

    # Check user limits
    if plan.user_limit is not None:
        user_service = UserService(db)
        user_count = await user_service.repository.count(organization_id=current_org.id)
        if user_count > plan.user_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change plan to '{plan.name}'. Current active users ({user_count}) exceeds limit of {plan.user_limit}.",
            )

    if account_type:
        if not current_org.others:
            current_org.others = {}
        current_org.others["account_type"] = account_type
        flag_modified(current_org, "others")

    current_org.plan_id = plan.id
    if hasattr(current_org, "subscription_plan"):
        try:
            from app.models.organization import SubscriptionPlan
            current_org.subscription_plan = SubscriptionPlan(tier_clean)
        except Exception:
            pass

    if tier_enum != PlanTier.FREE:
        current_org.subscription_status = "active"

    await db.commit()
    await db.refresh(current_org)

    return {
        "success": True,
        "message": f"Organization plan updated to {plan.name}.",
        "plan_id": current_org.plan_id,
        "plan_name": plan.name,
        "plan_tier": plan.tier.value,
        "subscription_status": current_org.subscription_status,
    }


@router.post(
    "/organization/request-trial-extension",
    summary="Request trial extension for your organization",
)
async def request_trial_extension_endpoint(
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.ADMIN])
    ),
    current_org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return {
        "success": True,
        "message": f"Trial extension request submitted for '{current_org.name}'. An administrator will review your request.",
    }
