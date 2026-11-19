"""Base repository with generic CRUD and multi-tenant isolation support"""

from datetime import datetime, timezone
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy import select, update, delete, func, insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import BaseModel


ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """Generic repository for async CRUD operations with soft-delete and tenant scoping"""

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get(
        self,
        id: int,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[ModelType]:
        """Get a single record by ID, optionally scoped to organization_id"""
        query = select(self.model).where(self.model.id == id)

        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

        if organization_id is not None and hasattr(self.model, "organization_id"):
            query = query.where(getattr(self.model, "organization_id") == organization_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_public_id(
        self,
        public_id: Any,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> Optional[ModelType]:
        """Get a single record by UUID public_id"""
        if not hasattr(self.model, "public_id"):
            return None
        query = select(self.model).where(getattr(self.model, "public_id") == public_id)
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        if organization_id is not None and hasattr(self.model, "organization_id"):
            query = query.where(getattr(self.model, "organization_id") == organization_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_fields(
        self,
        include_deleted: bool = False,
        **fields: Any,
    ) -> List[ModelType]:
        """Get records by multiple field filters"""
        query = select(self.model)
        for field, value in fields.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
        organization_id: Optional[int] = None,
    ) -> List[ModelType]:
        """Get multiple records with pagination and optional tenant filter"""
        query = select(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

        if organization_id is not None and hasattr(self.model, "organization_id"):
            query = query.where(getattr(self.model, "organization_id") == organization_id)

        query = query.order_by(self.model.id.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, obj_in: dict[str, Any]) -> ModelType:
        """Create a new record"""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def bulk_create(self, objects: List[dict[str, Any]]) -> List[ModelType]:
        """Create multiple records in one roundtrip"""
        if not objects:
            return []

        query = insert(self.model).values(objects).returning(self.model)
        result = await self.db.execute(query)
        await self.db.flush()
        return list(result.scalars().all())

    async def update(
        self,
        id: int,
        obj_in: dict[str, Any],
    ) -> Optional[ModelType]:
        """Update an existing record"""
        db_obj = await self.get(id)
        if not db_obj:
            return None

        for field, value in obj_in.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        await self.db.flush()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, id: int, soft: bool = True) -> bool:
        """Delete a record (soft delete by default)"""
        db_obj = await self.get(id, include_deleted=True)
        if not db_obj:
            return False

        if soft and hasattr(self.model, "is_deleted"):
            db_obj.soft_delete()
            await self.db.flush()
            return True
        else:
            query = delete(self.model).where(self.model.id == id)
            result = await self.db.execute(query)
            await self.db.flush()
            return (result.rowcount or 0) > 0

    async def bulk_soft_delete(self, ids: List[int]) -> int:
        """Soft-delete multiple records by ID"""
        if not ids:
            return 0
        query = (
            update(self.model)
            .where(self.model.id.in_(ids))
            .where(self.model.is_deleted == False)
            .values(is_deleted=True, deleted_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount or 0

    async def count(
        self,
        include_deleted: bool = False,
        filter_expr: Any = None,
        organization_id: Optional[int] = None,
    ) -> int:
        """Count total records matching filters"""
        query = select(func.count()).select_from(self.model)

        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

        if organization_id is not None and hasattr(self.model, "organization_id"):
            query = query.where(getattr(self.model, "organization_id") == organization_id)

        if filter_expr is not None:
            query = query.where(filter_expr)

        result = await self.db.execute(query)
        return result.scalar_one() or 0

    async def exists(self, id: int, organization_id: Optional[int] = None) -> bool:
        """Check if a record exists"""
        query = select(self.model.id).where(
            self.model.id == id,
            self.model.is_deleted == False,
        )
        if organization_id is not None and hasattr(self.model, "organization_id"):
            query = query.where(getattr(self.model, "organization_id") == organization_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
