"""User repository with multi-tenant queries"""

import uuid
from typing import Optional, List, Any, Union
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with multi-tenant filtering"""

    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_id(
        self,
        user_id: int,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[User]:
        """Lookup by primary key ID (supports both repo.get_by_id(id) and UserRepository.get_by_id(db, id))"""
        db = self if isinstance(self, AsyncSession) else self.db
        query = select(User).options(selectinload(User.organization)).where(User.id == user_id)
        if not include_deleted:
            query = query.where(User.is_deleted == False)
        if organization_id is not None:
            query = query.where(User.organization_id == organization_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_public_id(
        self,
        public_id: Any,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[User]:
        """Lookup by UUID public_id (supports both repo.get_by_public_id(pid) and UserRepository.get_by_public_id(db, pid))"""
        db = self if isinstance(self, AsyncSession) else self.db
        query = select(User).options(selectinload(User.organization)).where(User.public_id == public_id)
        if not include_deleted:
            query = query.where(User.is_deleted == False)
        if organization_id is not None:
            query = query.where(User.organization_id == organization_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def lookup_by_public_id(db: AsyncSession, public_id: Any) -> Optional[User]:
        """Static lookup helper by UUID public_id"""
        result = await db.execute(
            select(User).options(selectinload(User.organization)).where(User.public_id == public_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def lookup_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        """Static lookup helper by integer ID"""
        result = await db.execute(
            select(User).options(selectinload(User.organization)).where(User.id == user_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get(
        self,
        id: int,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[User]:
        """Get user by ID with eager-loaded organization"""
        query = select(User).options(selectinload(User.organization)).where(User.id == id)
        if not include_deleted:
            query = query.where(User.is_deleted == False)
        if organization_id is not None:
            query = query.where(User.organization_id == organization_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        email: str,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[User]:
        """Get user by email, optionally scoped to an organization"""
        query = (
            select(User)
            .options(selectinload(User.organization))
            .where(User.email == email.lower().strip())
        )
        if not include_deleted:
            query = query.where(User.is_deleted == False)
        if organization_id is not None:
            query = query.where(User.organization_id == organization_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username(
        self,
        username: str,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[User]:
        """Get user by username, optionally scoped to an organization"""
        query = (
            select(User)
            .options(selectinload(User.organization))
            .where(User.username == username.strip())
        )
        if not include_deleted:
            query = query.where(User.is_deleted == False)
        if organization_id is not None:
            query = query.where(User.organization_id == organization_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
        role: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[User]:
        """Get multiple users with tenant isolation, role, and search filters"""
        stmt = select(User)
        if not include_deleted:
            stmt = stmt.where(User.is_deleted == False)

        if organization_id is not None:
            stmt = stmt.where(User.organization_id == organization_id)

        if role:
            stmt = stmt.where(User.role == role)

        if search:
            search_filter = (
                User.full_name.ilike(f"%{search}%")
                | User.email.ilike(f"%{search}%")
                | User.username.ilike(f"%{search}%")
                | User.mobile.ilike(f"%{search}%")
                | User.department.ilike(f"%{search}%")
            )
            stmt = stmt.where(search_filter)

        stmt = stmt.order_by(User.id.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_users(
        self,
        query: Optional[str] = None,
        role: Optional[str] = None,
        organization_id: Optional[int] = None,
        limit: int = 10,
    ) -> List[User]:
        """Search users by name, email, or username within a tenant"""
        stmt = select(User).where(User.is_deleted == False)

        if organization_id is not None:
            stmt = stmt.where(User.organization_id == organization_id)

        if role:
            stmt = stmt.where(User.role == role)

        if query:
            search_filter = (
                User.full_name.ilike(f"%{query}%")
                | User.email.ilike(f"%{query}%")
                | User.username.ilike(f"%{query}%")
                | User.mobile.ilike(f"%{query}%")
            )
            stmt = stmt.where(search_filter)

        result = await self.db.execute(stmt.limit(limit))
        return list(result.scalars().all())
