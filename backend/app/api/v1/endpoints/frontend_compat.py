"""Frontend integration endpoints for Onboarding, Super-Admin Organizations Console, Notifications, and AI Credits"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user, get_current_superuser, get_current_organization
from app.models.organization import Organization, SubscriptionPlan
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.organization_service import OrganizationService, slugify
from app.services.user_service import UserService

router = APIRouter()


def _serialize_org_for_console(org: Organization, user_count: int = 0) -> dict:
    """Serialize Organization into the shape expected by the Super-Admin OrgConsole and Auth User"""
    settings_dict = org.settings or {}
    account_type = settings_dict.get("account_type", "organization")
    plan_str = org.subscription_plan.value if hasattr(org.subscription_plan, "value") else str(org.subscription_plan)
    return {
        "id": org.id,
        "public_id": str(org.public_id),
        "name": org.name,
        "slug": org.slug,
        "location": org.address or settings_dict.get("location") or "Chennai, India",
        "is_active": org.is_active,
        "is_parent": org.is_parent,
        "parent_id": org.parent_id,
        "subscription_status": settings_dict.get("subscription_status", "active"),
        "subscription_plan": plan_str,
        "plan_name": plan_str.capitalize(),
        "user_count": user_count,
        "user_limit": org.max_users,
        "max_users": org.max_users,
        "account_type": account_type,
        "others": settings_dict,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
    }


# ── 1. Onboarding & Real-Time Availability Checks ───────────────────────────

@router.get("/onboard/check-org", tags=["Onboarding"])
async def check_org_name(
    name: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    slug = slugify(name)
    org_service = OrganizationService(db)
    existing = await org_service.get_organization_by_slug(slug)
    return {
        "available": existing is None,
        "slug": slug,
        "message": "Organization name is available." if existing is None else "Organization name is already registered.",
    }


@router.get("/onboard/check-username", tags=["Onboarding"])
async def check_username(
    username: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    clean = username.strip().lower()
    user_service = UserService(db)
    existing = await user_service.get_user_by_username(clean)
    suggestions = [f"{clean}_wv", f"{clean}01", f"{clean}_mis"] if existing else []
    return {
        "available": existing is None,
        "suggestions": suggestions,
        "message": "Username is available." if existing is None else "Username is already taken.",
    }


@router.get("/onboard/check-email", tags=["Onboarding"])
async def check_email(
    email: str = Query(..., min_length=3),
    db: AsyncSession = Depends(get_db),
):
    clean = email.strip().lower()
    user_service = UserService(db)
    existing = await user_service.get_user_by_email(clean)
    return {
        "available": existing is None,
        "message": "Email address is available." if existing is None else "Email address is already registered.",
    }


@router.post("/onboard", status_code=status.HTTP_201_CREATED, tags=["Onboarding"])
async def onboard_organization_and_admin(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Self-onboard a new organization (linked under parent org WinVinaya Infosystems) and its admin user."""
    org_info = payload.get("organization") or {}
    admin_info = payload.get("admin_user") or payload.get("admin") or {}

    org_name = (org_info.get("name") or settings.DEFAULT_ORGANIZATION_NAME).strip()
    org_location = org_info.get("location")
    metadata = org_info.get("metadata") or {}

    org_service = OrganizationService(db)
    parent_org = await org_service.get_or_create_default_organization()

    slug = slugify(org_name)
    existing_org = await org_service.get_organization_by_slug(slug)
    if existing_org:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    new_org = await org_service.repository.create({
        "name": org_name,
        "slug": slug,
        "parent_id": parent_org.id,
        "is_parent": False,
        "address": org_location,
        "subscription_plan": SubscriptionPlan.PROFESSIONAL,
        "is_active": True,
        "max_users": 100,
        "settings": {
            **metadata,
            "location": org_location,
            "subscription_status": "active",
        },
    })

    user_service = UserService(db)
    user_in = UserCreate(
        email=admin_info["email"],
        username=admin_info["username"],
        full_name=admin_info.get("full_name"),
        password=admin_info.get("password") or "Welcome@123",
        role=UserRole.ORG_ADMIN,
        is_active=True,
        is_verified=True,
    )
    user = await user_service.create_user(user_in, forced_organization_id=new_org.id)

    return {
        "success": True,
        "message": "Organization and administrator account created successfully!",
        "organization": _serialize_org_for_console(new_org, user_count=1),
        "user": UserResponse.model_validate(user),
    }


@router.patch("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def patch_current_user_profile(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile fields via PATCH /api/v1/auth/me."""
    user_service = UserService(db)
    update_in = UserUpdate(
        full_name=payload.get("full_name", current_user.full_name),
        mobile=payload.get("phone", current_user.mobile),
        designation=payload.get("job_title", current_user.designation),
        avatar_url=payload.get("avatar", current_user.avatar_url),
    )
    return await user_service.update_user(current_user.id, update_in)


# ── 2. Super-Admin Organizations Console (/api/v1/admin/*) ──────────────────

async def _resolve_org_by_ref(db: AsyncSession, org_ref: str) -> Organization:
    org_service = OrganizationService(db)
    if org_ref.isdigit():
        return await org_service.get_organization(int(org_ref))
    try:
        parsed_uuid = uuid.UUID(org_ref)
        org = await org_service.repository.get_by_public_id(parsed_uuid)
        if org:
            return org
    except ValueError:
        pass
    org = await org_service.get_organization_by_slug(org_ref)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.get("/admin/organizations", tags=["Super Admin Console"])
async def admin_list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = Query(None),
    account_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    skip = (page - 1) * page_size
    orgs, total = await org_service.list_organizations(skip=skip, limit=page_size, search=search)

    # Count users per organization
    counts_res = await db.execute(
        select(User.organization_id, func.count(User.id))
        .where(User.is_deleted == False)
        .group_by(User.organization_id)
    )
    user_counts = {org_id: cnt for org_id, cnt in counts_res.all()}

    items = [
        _serialize_org_for_console(o, user_count=user_counts.get(o.id, 0))
        for o in orgs
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/admin/organizations", status_code=status.HTTP_201_CREATED, tags=["Super Admin Console"])
async def admin_create_organization(
    payload: dict,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org_info = payload.get("organization") or {}
    admin_info = payload.get("admin") or {}

    org_name = (org_info.get("name") or "New Organization").strip()
    org_location = org_info.get("location")

    org_service = OrganizationService(db)
    parent_org = await org_service.get_or_create_default_organization()

    slug = slugify(org_name)
    existing = await org_service.get_organization_by_slug(slug)
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    new_org = await org_service.repository.create({
        "name": org_name,
        "slug": slug,
        "parent_id": parent_org.id,
        "is_parent": False,
        "address": org_location,
        "subscription_plan": SubscriptionPlan.ENTERPRISE,
        "is_active": True,
        "max_users": 100,
        "settings": {
            "location": org_location,
            "account_type": "organization",
            "subscription_status": "active",
        },
    })

    user_service = UserService(db)
    admin_user = await user_service.create_user(
        UserCreate(
            email=admin_info["email"],
            username=admin_info["username"],
            full_name=admin_info.get("full_name"),
            password=admin_info.get("password") or "Welcome@123",
            role=UserRole.ORG_ADMIN,
            is_active=True,
            is_verified=True,
        ),
        forced_organization_id=new_org.id,
    )

    return {
        "success": True,
        "message": f"Organization '{new_org.name}' and admin account provisioned.",
        "organization": _serialize_org_for_console(new_org, user_count=1),
        "admin_user": UserResponse.model_validate(admin_user),
    }


@router.post("/admin/organizations/{org_ref}/deactivate", tags=["Super Admin Console"])
async def admin_deactivate_organization(
    org_ref: str,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org = await _resolve_org_by_ref(db, org_ref)
    org.is_active = False
    await db.flush()
    await db.refresh(org)
    return _serialize_org_for_console(org)


@router.post("/admin/organizations/{org_ref}/reactivate", tags=["Super Admin Console"])
async def admin_reactivate_organization(
    org_ref: str,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org = await _resolve_org_by_ref(db, org_ref)
    org.is_active = True
    await db.flush()
    await db.refresh(org)
    return _serialize_org_for_console(org)


@router.post("/admin/organizations/{org_ref}/extend-trial", tags=["Super Admin Console"])
async def admin_extend_organization_trial(
    org_ref: str,
    payload: dict,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org = await _resolve_org_by_ref(db, org_ref)
    return _serialize_org_for_console(org)


@router.delete("/admin/organizations/{org_ref}", tags=["Super Admin Console"])
async def admin_delete_organization(
    org_ref: str,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org = await _resolve_org_by_ref(db, org_ref)
    if org.is_parent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the root parent organization (WinVinaya Infosystems)",
        )
    serialized = _serialize_org_for_console(org)
    org_service = OrganizationService(db)
    await org_service.delete_organization(org.id)
    return serialized


@router.get("/admin/organizations/{org_ref}/users", tags=["Super Admin Console"])
async def admin_get_organization_users(
    org_ref: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    org = await _resolve_org_by_ref(db, org_ref)
    user_service = UserService(db)
    skip = (page - 1) * page_size
    users = await user_service.get_users(skip=skip, limit=page_size, organization_id=org.id)
    total = await user_service.repository.count(organization_id=org.id)
    return {
        "items": [UserResponse.model_validate(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/admin/stats", tags=["Super Admin Console"])
async def admin_get_platform_stats(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    total_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False))).scalar() or 0
    inactive_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.is_active == False))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)).where(User.is_deleted == False))).scalar() or 0
    avg_users = round(total_users / total_orgs, 1) if total_orgs > 0 else 0.0

    return {
        "total_organizations": total_orgs,
        "active_trials": 0,
        "total_users": total_users,
        "avg_users_per_org": avg_users,
        "inactive_organizations": inactive_orgs,
        "expired_trials": 0,
        "paid_organizations": total_orgs - inactive_orgs,
        "paid_users": total_users,
        "team_organizations": total_orgs,
        "individual_organizations": 0,
    }


@router.get("/admin/system-health", tags=["Super Admin Console"])
async def admin_get_system_health(
    current_user: User = Depends(get_current_superuser),
):
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "metrics": [
            {"name": "PostgreSQL (wvismis)", "status": "operational", "responseTime": 2},
            {"name": "FastAPI MVC API v1", "status": "operational", "responseTime": 1},
            {"name": "WebSockets Streamer", "status": "operational", "responseTime": 1},
            {"name": "Harness Agentic AI", "status": "operational", "responseTime": 4},
        ],
    }


# ── 3. Notifications & AI Credits Endpoints ─────────────────────────────────

@router.get("/notifications", tags=["Notifications"])
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/notifications/unread-count", tags=["Notifications"])
async def get_unread_notifications_count(
    current_user: User = Depends(get_current_user),
):
    return {"unread_count": 0}


@router.patch("/notifications/mark-all-read", tags=["Notifications"])
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
):
    return {"marked_read": 0}


@router.patch("/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    return {
        "id": 1,
        "public_id": notification_id,
        "type": "lead_assigned",
        "title": "Notification",
        "message": "",
        "is_read": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ai/credits", tags=["Harness Agentic AI"])
async def get_ai_credit_balance(
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "balance": 5000,
        "granted": 5000,
        "period_start": period_start.isoformat(),
        "percent_used": 0,
    }


@router.get("/ai/usage", tags=["Harness Agentic AI"])
async def get_ai_usage_summary(
    scope: str = Query("mine"),
    current_user: User = Depends(get_current_user),
):
    return {
        "total_tokens_used": 0,
        "total_credits_consumed": 0,
        "total_calls": 0,
        "by_provider": [],
        "by_model": [],
        "by_action_type": [],
        "daily_trend": [],
    }
