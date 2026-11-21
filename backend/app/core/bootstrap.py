"""Bootstrap module to initialize pricing plans, parent organization, and superuser on startup"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.organization import Organization, SubscriptionPlan
from app.models.plan import Plan, PlanTier, Module
from app.models.user import User, UserRole


PLAN_DEFINITIONS = {
    PlanTier.FREE: {
        "name": "Free",
        "enabled_modules": [
            Module.PROJECT_MANAGEMENT.value,
        ],
        "ai_credits_monthly": 100,
        "user_limit": 10,
        "price_per_user": 0,
    },
    PlanTier.BASIC: {
        "name": "Basic",
        "enabled_modules": [
            Module.PROJECT_MANAGEMENT.value,
            Module.TIMESHEET_MANAGEMENT.value,
            Module.CRM_MANAGEMENT.value,
            Module.REPORTS_MANAGEMENT.value,
        ],
        "ai_credits_monthly": 500,
        "user_limit": 20,
        "price_per_user": 149,
    },
    PlanTier.PRO: {
        "name": "Pro",
        "enabled_modules": [
            Module.PROJECT_MANAGEMENT.value,
            Module.TIMESHEET_MANAGEMENT.value,
            Module.CRM_MANAGEMENT.value,
            Module.REPORTS_MANAGEMENT.value,
            Module.CANDIDATE_MANAGEMENT.value,
            Module.PLACEMENT_MANAGEMENT.value,
            Module.HR_MANAGEMENT.value,
        ],
        "ai_credits_monthly": 1000,
        "user_limit": 50,
        "price_per_user": 299,
    },
    PlanTier.ENTERPRISE: {
        "name": "Enterprise",
        "enabled_modules": [m.value for m in Module],
        "ai_credits_monthly": 2000,
        "user_limit": 100,
        "price_per_user": 499,
    },
}


async def seed_plans(db: AsyncSession) -> dict[PlanTier, Plan]:
    """Ensure the Free/Basic/Pro/Enterprise pricing plans exist and match PLAN_DEFINITIONS."""
    plans = {}
    for tier, definition in PLAN_DEFINITIONS.items():
        result = await db.execute(select(Plan).where(Plan.tier == tier))
        plan = result.scalars().first()
        if not plan:
            plan = Plan(tier=tier, **definition)
            db.add(plan)
            await db.flush()
            logger.info(f"Seeded pricing plan: {definition['name']} ({tier.value})")
        else:
            plan.name = definition["name"]
            plan.enabled_modules = definition["enabled_modules"]
            plan.ai_credits_monthly = definition["ai_credits_monthly"]
            plan.user_limit = definition["user_limit"]
            plan.price_per_user = definition["price_per_user"]
        plans[tier] = plan
    await db.commit()
    return plans


async def init_parent_org_and_superuser(db: AsyncSession) -> tuple[Organization, User]:
    """
    Ensure the pricing plans, parent organization ('WinVinaya Infosystems'), and root superuser
    ('dharanidaran.a@winvinaya.com') are initialized in the database.
    """
    # 1. Seed pricing plans
    plans = await seed_plans(db)
    enterprise_plan = plans.get(PlanTier.ENTERPRISE)

    # 2. Ensure Parent Organization (WinVinaya Infosystems)
    parent_slug = settings.DEFAULT_ORGANIZATION_SLUG.lower().strip()
    result = await db.execute(select(Organization).where(Organization.slug == parent_slug))
    parent_org = result.scalar_one_or_none()

    if not parent_org:
        logger.info(f"Creating root parent organization: '{settings.DEFAULT_ORGANIZATION_NAME}' ({parent_slug})")
        parent_org = Organization(
            name=settings.DEFAULT_ORGANIZATION_NAME,
            slug=parent_slug,
            domain="winvinaya.com",
            description="Parent Organization for WinVinaya MIS Platform",
            subscription_plan=SubscriptionPlan.ENTERPRISE,
            plan_id=enterprise_plan.id if enterprise_plan else None,
            subscription_status="active",
            is_active=True,
            is_parent=True,
            max_users=100,
            settings={
                "is_default_tenant": True,
                "is_parent_org": True,
                "platform": "wvismis",
            },
            others={
                "account_type": "organization",
            },
        )
        db.add(parent_org)
        await db.commit()
        await db.refresh(parent_org)
        logger.success(f"Parent organization created: id={parent_org.id}, name='{parent_org.name}'")
    else:
        # Guarantee is_parent flag and plan are set
        updated_org = False
        if not parent_org.is_parent:
            parent_org.is_parent = True
            updated_org = True
        if enterprise_plan and parent_org.plan_id != enterprise_plan.id:
            parent_org.plan_id = enterprise_plan.id
            updated_org = True
        if not getattr(parent_org, "subscription_status", None):
            parent_org.subscription_status = "active"
            updated_org = True
        if parent_org.max_users != 100:
            parent_org.max_users = 100
            updated_org = True
        if updated_org:
            await db.commit()
            await db.refresh(parent_org)

    # 3. Ensure Superuser (dharanidaran.a@winvinaya.com)
    superuser_email = settings.FIRST_SUPERUSER.lower().strip()
    user_result = await db.execute(select(User).where(User.email == superuser_email))
    superuser = user_result.scalar_one_or_none()

    if not superuser:
        logger.info(f"Creating default superuser: '{superuser_email}' associated with parent org '{parent_org.name}'")
        superuser = User(
            email=superuser_email,
            username=superuser_email.split("@")[0].strip(),
            full_name="Dharanidaran A",
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            is_active=True,
            is_superuser=True,
            is_verified=True,
            role=UserRole.SUPER_ADMIN,
            organization_id=parent_org.id,
            department="Executive Management",
            designation="Super Administrator",
        )
        db.add(superuser)
        await db.commit()
        await db.refresh(superuser)
        logger.success(f"Superuser initialized: id={superuser.id}, email='{superuser.email}', org_id={superuser.organization_id}")
    else:
        # Ensure superuser flags and org association are up to date
        updated = False
        if not superuser.is_superuser:
            superuser.is_superuser = True
            updated = True
        if superuser.role != UserRole.SUPER_ADMIN:
            superuser.role = UserRole.SUPER_ADMIN
            updated = True
        if superuser.organization_id != parent_org.id:
            superuser.organization_id = parent_org.id
            updated = True
        if updated:
            await db.commit()
            await db.refresh(superuser)
            logger.info(f"Superuser '{superuser_email}' updated with parent org association")

    # Clean up previous placeholder admin if it existed
    if superuser_email != "admin@winvinaya.com":
        old_admin_res = await db.execute(select(User).where(User.email == "admin@winvinaya.com"))
        old_admin = old_admin_res.scalar_one_or_none()
        if old_admin and old_admin.is_superuser:
            old_admin.is_superuser = False
            old_admin.role = UserRole.ADMIN
            await db.commit()

    # Ensure every existing user in the database is associated with an organization
    await db.execute(
        update(User)
        .where(User.organization_id.is_(None))
        .values(organization_id=parent_org.id)
    )
    await db.commit()

    return parent_org, superuser
