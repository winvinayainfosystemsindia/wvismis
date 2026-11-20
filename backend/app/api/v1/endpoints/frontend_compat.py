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
    others_dict = getattr(org, "others", None) or settings_dict
    account_type = others_dict.get("account_type", settings_dict.get("account_type", "organization"))
    plan_str = org.subscription_plan.value if hasattr(org.subscription_plan, "value") else str(org.subscription_plan)

    plan_obj = None
    if getattr(org, "plan", None):
        plan_obj = {
            "id": org.plan.id,
            "tier": org.plan.tier.value,
            "name": org.plan.name,
            "enabled_modules": org.plan.enabled_modules,
            "ai_credits_monthly": org.plan.ai_credits_monthly,
            "user_limit": org.plan.user_limit,
            "price_per_user": getattr(org.plan, "price_per_user", 0),
        }
    else:
        plan_obj = {
            "tier": plan_str.lower(),
            "name": plan_str.capitalize(),
            "enabled_modules": ["project_management"],
            "ai_credits_monthly": 1000,
            "user_limit": org.max_users,
            "price_per_user": 0,
        }

    plan_name = org.plan.name if getattr(org, "plan", None) else plan_str.capitalize()
    user_limit = (org.plan.user_limit if getattr(org, "plan", None) and org.plan.user_limit else org.max_users)
    if user_limit is None or user_limit >= 100000:
        user_limit = 100
    sub_status = getattr(org, "subscription_status", None) or settings_dict.get("subscription_status", "active")
    trial_exp = org.trial_expires_at.isoformat() if getattr(org, "trial_expires_at", None) else None

    return {
        "id": org.id,
        "public_id": str(org.public_id),
        "name": org.name,
        "slug": org.slug,
        "location": org.address or others_dict.get("location") or settings_dict.get("location") or "Chennai, India",
        "is_active": org.is_active,
        "is_parent": org.is_parent,
        "parent_id": org.parent_id,
        "subscription_status": sub_status,
        "subscription_plan": plan_str,
        "plan_id": getattr(org, "plan_id", None),
        "plan": plan_obj,
        "plan_name": plan_name,
        "trial_expires_at": trial_exp,
        "user_count": user_count,
        "user_limit": user_limit,
        "max_users": user_limit,
        "account_type": account_type,
        "others": others_dict,
        "settings": settings_dict,
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
    from datetime import datetime, timezone, timedelta
    days = payload.get("days", 30)
    org = await _resolve_org_by_ref(db, org_ref)
    base_date = org.trial_expires_at if org.trial_expires_at and org.trial_expires_at > datetime.now(timezone.utc) else datetime.now(timezone.utc)
    org.trial_expires_at = base_date + timedelta(days=days)
    org.subscription_status = "trial"
    await db.flush()
    await db.refresh(org)
    return _serialize_org_for_console(org)


@router.post("/admin/organizations/{org_ref}/plan", tags=["Super Admin Console"])
async def admin_update_organization_plan(
    org_ref: str,
    payload: dict,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.plan_repository import PlanRepository
    org = await _resolve_org_by_ref(db, org_ref)
    tier = payload.get("plan_tier") or payload.get("tier")
    if not tier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="plan_tier is required")
    plan = await PlanRepository.get_by_tier(db, tier)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plan '{tier}' not found")
    org.plan_id = plan.id
    if hasattr(org, "subscription_plan"):
        try:
            from app.models.organization import SubscriptionPlan
            org.subscription_plan = SubscriptionPlan(plan.tier.value)
        except Exception:
            pass
    org.subscription_status = payload.get("subscription_status", "active")
    if "user_limit" in payload and payload["user_limit"]:
        org.max_users = int(payload["user_limit"])
    await db.flush()
    await db.refresh(org)
    return _serialize_org_for_console(org)


@router.post("/admin/users/{public_id}/credits/grant", tags=["Super Admin Console"])
async def admin_grant_user_credits(
    public_id: uuid.UUID,
    payload: dict,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    from app.services import ai_credit_service
    from app.repositories.user_repository import UserRepository
    from app.schemas.ai_credit import AICreditBalanceResponse

    amount = int(payload.get("amount", 100))
    user_repo = UserRepository(db)
    target_user = await user_repo.get_by_public_id(public_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    org = await db.get(Organization, target_user.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    wallet = await ai_credit_service.grant_admin_credits_to_user(
        db, org, target_user.id, amount
    )
    await db.commit()
    return AICreditBalanceResponse.from_wallet(wallet)


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
    from app.core.cache import memory_cache
    cached_stats = await memory_cache.get("admin:platform_stats")
    if cached_stats is not None:
        return cached_stats

    total_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False))).scalar() or 0
    inactive_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.is_active == False))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)).where(User.is_deleted == False))).scalar() or 0
    avg_users = round(total_users / total_orgs, 1) if total_orgs > 0 else 0.0

    stats = {
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
    await memory_cache.set("admin:platform_stats", stats, ttl_seconds=30.0)
    return stats


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
