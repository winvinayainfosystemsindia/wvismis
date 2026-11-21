#!/usr/bin/env python3
"""
WVISMIS - Superuser & Organization Setup Script
Creates or updates the root superuser and parent organization across
Development (wvismis_dev) and Production (wvismis_prod) environments.

Usage:
    # Run for development environment:
    python scripts/create_superuser.py --env dev

    # Run for production environment:
    python scripts/create_superuser.py --env prod

    # Run for both dev and prod environments:
    python scripts/create_superuser.py --env all

    # With optional API login verification:
    python scripts/create_superuser.py --env dev --verify-api
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure backend root is on Python module search path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import dotenv_values
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update
from passlib.context import CryptContext

# Default values requested
DEFAULT_FULL_NAME = "Dharanidaran A"
DEFAULT_EMAIL = "dharanidaran.a@winvinaya.com"
DEFAULT_PASSWORD = "Testpass@123"
DEFAULT_ORG_NAME = "WinVinaya InfoSystems"
DEFAULT_ORG_SLUG = "winvinaya"
DEFAULT_ORG_DOMAIN = "winvinaya.com"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def load_env_config(env_name: str) -> dict:
    """Load configuration dictionary from the corresponding .env.<env> file."""
    env_file = BACKEND_DIR / f".env.{env_name}"
    if not env_file.exists():
        fallback_file = BACKEND_DIR / ".env"
        if fallback_file.exists():
            print(f"⚠️  {env_file.name} not found, falling back to .env")
            env_file = fallback_file
        else:
            print(f"❌ Error: Neither {env_file.name} nor .env found in {BACKEND_DIR}")
            sys.exit(1)

    print(f"📄 Loaded environment configuration: {env_file.name}")
    config = dotenv_values(env_file)
    return config


def build_db_url(config: dict, env_name: str) -> str:
    """Construct asynchronous PostgreSQL connection URL."""
    db_user = config.get("POSTGRES_USER", "wvismis_user")
    db_pass = config.get("POSTGRES_PASSWORD", "winvinayamisdb2026")
    db_host = config.get("POSTGRES_SERVER", "localhost")
    db_port = config.get("POSTGRES_PORT", "5432")
    default_db = f"wvismis_{env_name}" if env_name in ("dev", "prod") else "wvismis_dev"
    db_name = config.get("POSTGRES_DB", default_db)

    return f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


async def setup_superuser_in_db(
    db: AsyncSession,
    full_name: str,
    email: str,
    password: str,
    org_name: str,
    org_slug: str,
    org_domain: str,
) -> tuple[int, int]:
    """
    Directly create or update the parent organization and superuser in the database.
    """
    from app.models.organization import Organization, SubscriptionPlan
    from app.models.plan import Plan, PlanTier, Module
    from app.models.user import User, UserRole

    # 1. Ensure Plans and Users schema compatibility
    from sqlalchemy import text
    await db.execute(
        text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='plans') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='plans' AND column_name='is_deleted') THEN
                    ALTER TABLE plans ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='plans' AND column_name='deleted_at') THEN
                    ALTER TABLE plans ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
                END IF;
            END IF;

            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users') THEN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='timezone') THEN
                    ALTER TABLE users ADD COLUMN timezone VARCHAR(64);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='reporting_manager_id') THEN
                    ALTER TABLE users ADD COLUMN reporting_manager_id INTEGER REFERENCES users(id) ON DELETE SET NULL;
                END IF;
            END IF;
        END $$;
        """)
    )
    await db.commit()

    plan_defs = {
        PlanTier.FREE: ("Free", [Module.PROJECT_MANAGEMENT.value], 100, 10, 0),
        PlanTier.BASIC: ("Basic", [Module.PROJECT_MANAGEMENT.value, Module.TIMESHEET_MANAGEMENT.value, Module.CRM_MANAGEMENT.value, Module.REPORTS_MANAGEMENT.value], 500, 20, 149),
        PlanTier.PRO: ("Pro", [Module.PROJECT_MANAGEMENT.value, Module.TIMESHEET_MANAGEMENT.value, Module.CRM_MANAGEMENT.value, Module.REPORTS_MANAGEMENT.value, Module.CANDIDATE_MANAGEMENT.value, Module.PLACEMENT_MANAGEMENT.value, Module.HR_MANAGEMENT.value], 1000, 50, 299),
        PlanTier.ENTERPRISE: ("Enterprise", [m.value for m in Module], 2000, 100, 499),
    }

    enterprise_plan_id = None
    for tier, (pname, pmodules, credits, ulimit, price) in plan_defs.items():
        res = await db.execute(select(Plan).where(Plan.tier == tier))
        plan = res.scalars().first()
        if not plan:
            plan = Plan(
                tier=tier,
                name=pname,
                enabled_modules=pmodules,
                ai_credits_monthly=credits,
                user_limit=ulimit,
                price_per_user=price,
            )
            db.add(plan)
            await db.flush()
        if tier == PlanTier.ENTERPRISE:
            enterprise_plan_id = plan.id

    # 2. Ensure Parent Organization
    clean_slug = org_slug.lower().strip()
    org_res = await db.execute(select(Organization).where(Organization.slug == clean_slug))
    org = org_res.scalar_one_or_none()

    if not org:
        org = Organization(
            name=org_name,
            slug=clean_slug,
            domain=org_domain,
            description="Parent Organization for WinVinaya MIS Platform",
            subscription_plan=SubscriptionPlan.ENTERPRISE,
            plan_id=enterprise_plan_id,
            subscription_status="active",
            is_active=True,
            is_parent=True,
            max_users=100,
            settings={
                "is_default_tenant": True,
                "is_parent_org": True,
                "platform": "wvismis",
            },
            others={"account_type": "organization"},
        )
        db.add(org)
        await db.flush()
        print(f"  🏢 Created parent organization: '{org.name}' (id={org.id}, slug='{org.slug}')")
    else:
        org.name = org_name
        org.is_parent = True
        org.is_active = True
        org.subscription_status = "active"
        if enterprise_plan_id and not org.plan_id:
            org.plan_id = enterprise_plan_id
        await db.flush()
        print(f"  🏢 Found existing parent organization: '{org.name}' (id={org.id})")

    # 3. Ensure Superuser
    clean_email = email.lower().strip()
    username = clean_email.split("@")[0].strip()
    hashed_pwd = get_password_hash(password)

    user_res = await db.execute(select(User).where(User.email == clean_email))
    user = user_res.scalar_one_or_none()

    if not user:
        user = User(
            email=clean_email,
            username=username,
            full_name=full_name,
            hashed_password=hashed_pwd,
            is_active=True,
            is_superuser=True,
            is_verified=True,
            role=UserRole.SUPER_ADMIN,
            organization_id=org.id,
            department="Executive Management",
            designation="Super Administrator",
        )
        db.add(user)
        await db.flush()
        print(f"  👤 Created new superuser: '{user.email}' (id={user.id}, role={user.role.value})")
    else:
        user.full_name = full_name
        user.hashed_password = hashed_pwd
        user.is_superuser = True
        user.is_active = True
        user.is_verified = True
        user.role = UserRole.SUPER_ADMIN
        user.organization_id = org.id
        await db.flush()
        print(f"  👤 Updated existing user to superuser: '{user.email}' (id={user.id}, role={user.role.value})")

    await db.commit()
    return org.id, user.id


async def verify_via_api(base_url: str, email: str, password: str, org_slug: str):
    """Verify that the superuser can authenticate via the FastAPI auth endpoint."""
    import httpx

    login_url = f"{base_url.rstrip('/')}/api/v1/auth/login"
    payload = {
        "email": email,
        "password": password,
        "organization_slug": org_slug,
    }

    print(f"  🌐 Testing API authentication against: {login_url}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(login_url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token", "")
                user_info = data.get("user", {})
                print("  ✅ API Login Successful!")
                print(f"     - User: {user_info.get('full_name')} ({user_info.get('email')})")
                print(f"     - Role: {user_info.get('role')} | is_superuser: {user_info.get('is_superuser')}")
                print(f"     - Token preview: {token[:25]}... (valid JWT)")
            else:
                print(f"  ⚠️  API Login returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"  ⚠️  Could not reach API server at {base_url}: {e}")
        print("     (Note: Ensure backend service is running if testing API login)")


async def process_environment(
    env_name: str,
    full_name: str,
    email: str,
    password: str,
    org_name: str,
    org_slug: str,
    org_domain: str,
    verify_api: bool = False,
    api_url: Optional[str] = None,
):
    """Execute setup for one specific environment (dev or prod)."""
    print(f"\n=======================================================")
    print(f"🚀 Setting up Superuser for Environment: [{env_name.upper()}]")
    print(f"=======================================================")

    config = load_env_config(env_name)
    db_url = build_db_url(config, env_name)
    print(f"🔌 Connecting to database: {db_url.split('@')[-1]}")

    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with session_factory() as session:
            org_id, user_id = await setup_superuser_in_db(
                db=session,
                full_name=full_name,
                email=email,
                password=password,
                org_name=org_name,
                org_slug=org_slug,
                org_domain=org_domain,
            )
            print(f"✨ Successfully provisioned {env_name.upper()} database.")
            print(f"   Organization ID: {org_id} | User ID: {user_id}")
    finally:
        await engine.dispose()

    if verify_api:
        if not api_url:
            port = 8000 if env_name == "dev" else 8002
            api_url = f"http://127.0.0.1:{port}"
        await verify_via_api(api_url, email, password, org_slug)


def main():
    parser = argparse.ArgumentParser(
        description="Provision WVISMIS Parent Organization and Superuser for Dev and Prod."
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod", "all"],
        default="all",
        help="Target environment: 'dev', 'prod', or 'all' (default: all)",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_FULL_NAME,
        help=f"Full name of superuser (default: '{DEFAULT_FULL_NAME}')",
    )
    parser.add_argument(
        "--email",
        default=DEFAULT_EMAIL,
        help=f"Email address of superuser (default: '{DEFAULT_EMAIL}')",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"Password for superuser (default: '{DEFAULT_PASSWORD}')",
    )
    parser.add_argument(
        "--org",
        default=DEFAULT_ORG_NAME,
        help=f"Parent Organization name (default: '{DEFAULT_ORG_NAME}')",
    )
    parser.add_argument(
        "--slug",
        default=DEFAULT_ORG_SLUG,
        help=f"Organization slug (default: '{DEFAULT_ORG_SLUG}')",
    )
    parser.add_argument(
        "--verify-api",
        action="store_true",
        help="Attempt API login verification after database provisioning",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Optional base URL for API login verification (e.g. http://127.0.0.1:8000 or https://dev-mis.winvinaya.com)",
    )

    args = parser.parse_args()

    target_envs = ["dev", "prod"] if args.env == "all" else [args.env]

    for env_name in target_envs:
        asyncio.run(
            process_environment(
                env_name=env_name,
                full_name=args.name,
                email=args.email,
                password=args.password,
                org_name=args.org,
                org_slug=args.slug,
                org_domain=DEFAULT_ORG_DOMAIN,
                verify_api=args.verify_api,
                api_url=args.api_url,
            )
        )

    print("\n🎉 All requested environments provisioned successfully!\n")


if __name__ == "__main__":
    main()
