"""User service — business logic for multi-tenant user operations and authentication"""

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.models.organization import Organization, SubscriptionPlan
from app.schemas.user import UserCreate, UserUpdate
from app.repositories.user_repository import UserRepository
from app.services.organization_service import OrganizationService, slugify
from app.core.security import get_password_hash, verify_password


class UserService:
    """Service for user-related business logic with multi-tenant isolation"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = UserRepository(db)
        self.org_service = OrganizationService(db)

    async def get_user(
        self,
        user_id: int,
        organization_id: Optional[int] = None,
    ) -> User:
        """Get user by ID, optionally enforcing tenant match"""
        user = await self.repository.get(user_id, organization_id=organization_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return await self.repository.get_by_email(email)

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return await self.repository.get_by_username(username)

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        organization_id: Optional[int] = None,
        role: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[User]:
        """Get list of users scoped to organization_id"""
        return await self.repository.get_multi(
            skip=skip,
            limit=limit,
            organization_id=organization_id,
            role=role,
            search=search,
        )

    async def _resolve_organization_for_registration(self, user_in: UserCreate) -> tuple[Organization, bool]:
        """
        Resolve or create the Organization (Tenant) for a user registration:
        1. If organization_name is supplied, create a new tenant organization (or join if slug exists).
        2. Else if organization_id is supplied, join that organization.
        3. Else if organization_slug is supplied, join that organization.
        4. Else join (or bootstrap) the default organization.
        Returns (organization, created_new_org).
        """
        if user_in.organization_name:
            slug = (user_in.organization_slug or slugify(user_in.organization_name)).lower().strip()
            existing = await self.org_service.get_organization_by_slug(slug)
            if existing:
                await self.org_service.validate_tenant_capacity(existing.id)
                return existing, False
            new_org = await self.org_service.repository.create({
                "name": user_in.organization_name.strip(),
                "slug": slug,
                "subscription_plan": SubscriptionPlan.PROFESSIONAL,
                "is_active": True,
                "max_users": 100,
                "settings": {},
            })
            return new_org, True

        if user_in.organization_id:
            org = await self.org_service.validate_tenant_capacity(user_in.organization_id)
            return org, False

        if user_in.organization_slug:
            org = await self.org_service.get_organization_by_slug(user_in.organization_slug)
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Organization with slug '{user_in.organization_slug}' not found",
                )
            await self.org_service.validate_tenant_capacity(org.id)
            return org, False

        default_org = await self.org_service.get_or_create_default_organization()
        await self.org_service.validate_tenant_capacity(default_org.id)
        return default_org, False

    async def create_user(
        self,
        user_in: UserCreate,
        forced_organization_id: Optional[int] = None,
    ) -> User:
        """Create a new user with multi-tenant resolution"""
        email_clean = user_in.email.lower().strip()
        existing_user = await self.repository.get_by_email(email_clean)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        existing_username = await self.repository.get_by_username(user_in.username.strip())
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

        created_new_org = False
        if forced_organization_id is not None:
            org = await self.org_service.validate_tenant_capacity(forced_organization_id)
        else:
            org, created_new_org = await self._resolve_organization_for_registration(user_in)

        user_data = user_in.model_dump(
            exclude={"password", "organization_id", "organization_slug", "organization_name"}
        )
        user_data["email"] = email_clean
        user_data["username"] = user_in.username.strip()
        user_data["hashed_password"] = get_password_hash(user_in.password)
        user_data["organization_id"] = org.id

        # If user created a brand new organization during self-registration, make them ORG_ADMIN
        if created_new_org and user_data.get("role") == UserRole.USER:
            user_data["role"] = UserRole.ORG_ADMIN

        user = await self.repository.create(user_data)
        return user

    async def update_user(
        self,
        user_id: int,
        user_in: UserUpdate,
        organization_id: Optional[int] = None,
    ) -> User:
        """Update user profile or role within tenant boundaries"""
        user = await self.get_user(user_id, organization_id=organization_id)
        update_data = user_in.model_dump(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        else:
            update_data.pop("password", None)

        if "email" in update_data and update_data["email"].lower().strip() != user.email:
            new_email = update_data["email"].lower().strip()
            existing_email = await self.repository.get_by_email(new_email)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )
            update_data["email"] = new_email

        if "username" in update_data and update_data["username"].strip() != user.username:
            new_username = update_data["username"].strip()
            existing_username = await self.repository.get_by_username(new_username)
            if existing_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )
            update_data["username"] = new_username

        updated_user = await self.repository.update(user_id, update_data)
        return updated_user

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> User:
        """Verify current password and update to new password"""
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        hashed = get_password_hash(new_password)
        return await self.repository.update(user.id, {"hashed_password": hashed})

    async def delete_user(
        self,
        user_id: int,
        organization_id: Optional[int] = None,
    ) -> bool:
        """Soft-delete user within tenant scope"""
        await self.get_user(user_id, organization_id=organization_id)
        return await self.repository.delete(user_id, soft=True)

    async def authenticate(
        self,
        email: str,
        password: str,
        organization_slug: Optional[str] = None,
    ) -> Optional[User]:
        """Authenticate user with email, password, and optional organization slug"""
        user = await self.repository.get_by_email(email.lower().strip())
        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        if organization_slug and user.organization:
            if user.organization.slug != organization_slug.lower().strip() and not user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User does not belong to organization '{organization_slug}'",
                )

        if user.organization and not user.organization.is_active and not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Organization '{user.organization.name}' is currently inactive",
            )

        # Record last_login_at
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        return user
