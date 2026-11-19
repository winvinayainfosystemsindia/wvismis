"""Bootstrap module to initialize parent organization and superuser on startup"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.organization import Organization, SubscriptionPlan
from app.models.user import User, UserRole


async def init_parent_org_and_superuser(db: AsyncSession) -> tuple[Organization, User]:
    """
    Ensure the parent organization ('WinVinaya Infosystems') and the root superuser
    ('dharanidaran.a@winvinaya.com') are initialized in the database.
    Every user in WVISMIS must be associated with an organization; regular users
    default to the parent organization if not registered under a specific tenant.
    """
    # 1. Ensure Parent Organization (WinVinaya Infosystems)
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
            is_active=True,
            is_parent=True,
            max_users=100000,
            settings={
                "is_default_tenant": True,
                "is_parent_org": True,
                "platform": "wvismis",
            },
        )
        db.add(parent_org)
        await db.commit()
        await db.refresh(parent_org)
        logger.success(f"Parent organization created: id={parent_org.id}, name='{parent_org.name}'")
    else:
        # Guarantee is_parent flag is set
        if not parent_org.is_parent:
            parent_org.is_parent = True
            await db.commit()
            await db.refresh(parent_org)

    # 2. Ensure Superuser (dharanidaran.a@winvinaya.com)
    superuser_email = settings.FIRST_SUPERUSER.lower().strip()
    user_result = await db.execute(select(User).where(User.email == superuser_email))
    superuser = user_result.scalar_one_or_none()

    if not superuser:
        logger.info(f"Creating default superuser: '{superuser_email}' associated with parent org '{parent_org.name}'")
        superuser = User(
            email=superuser_email,
            username=superuser_email.split("@")[0].strip(),
            full_name="Dharanidaran A (Super Admin)",
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

    return parent_org, superuser
