"""Activity tracking utilities for logging multi-tenant API operations"""

import uuid
from enum import Enum
from typing import Optional, Any, Dict
from datetime import datetime, date, time
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.activity_log import ActionType
from app.services.activity_log_service import ActivityLogService


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return None


def get_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request"""
    return request.headers.get("User-Agent")


def _serialize_val(val: Any) -> Any:
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, (uuid.UUID, datetime, date, time)):
        return val.isoformat() if hasattr(val, "isoformat") else str(val)
    return val


def get_changes(before: Any, after: Any) -> Optional[Dict[str, Any]]:
    """Compute changed fields between before and after objects"""
    if before is None and after is None:
        return None

    if hasattr(before, "dict"):
        before_dict = before.dict()
    elif hasattr(before, "__dict__"):
        before_dict = {k: v for k, v in before.__dict__.items() if not k.startswith("_")}
    else:
        before_dict = before or {}

    if hasattr(after, "dict"):
        after_dict = after.dict()
    elif hasattr(after, "__dict__"):
        after_dict = {k: v for k, v in after.__dict__.items() if not k.startswith("_")}
    else:
        after_dict = after or {}

    sensitive_fields = {"password", "hashed_password", "token", "secret", "api_key"}

    before_filtered = {}
    after_filtered = {}

    all_keys = set(before_dict.keys()) | set(after_dict.keys())
    for key in all_keys:
        if key in sensitive_fields:
            continue

        before_val = _serialize_val(before_dict.get(key))
        after_val = _serialize_val(after_dict.get(key))

        if before_val != after_val:
            before_filtered[key] = before_val
            after_filtered[key] = after_val

    if not before_filtered and not after_filtered:
        return None

    return {"before": before_filtered, "after": after_filtered}


def extract_safe_metadata(obj: Any) -> Optional[Dict[str, Any]]:
    """Extract safe metadata from an object, filtering sensitive fields"""
    if obj is None:
        return None

    if hasattr(obj, "dict"):
        obj_dict = obj.dict()
    elif hasattr(obj, "__dict__"):
        obj_dict = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    else:
        obj_dict = obj if isinstance(obj, dict) else {}

    sensitive_fields = {"password", "hashed_password", "token", "secret", "api_key"}
    filtered = {}

    for k, v in obj_dict.items():
        if k in sensitive_fields:
            continue
        filtered[k] = _serialize_val(v)

    return filtered if filtered else None


async def log_create(
    db: AsyncSession,
    request: Request,
    user_id: Optional[int],
    resource_type: str,
    resource_id: int,
    organization_id: Optional[int] = None,
    created_object: Optional[Any] = None,
    status_code: int = 201,
) -> None:
    """Log a CREATE action"""
    activity_service = ActivityLogService(db)
    metadata = extract_safe_metadata(created_object) if created_object else None

    await activity_service.log_activity(
        organization_id=organization_id,
        user_id=user_id,
        action_type=ActionType.CREATE,
        endpoint=str(request.url.path),
        method=request.method,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=metadata,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status_code=status_code,
    )


async def log_update(
    db: AsyncSession,
    request: Request,
    user_id: Optional[int],
    resource_type: str,
    resource_id: int,
    before: Any,
    after: Any,
    organization_id: Optional[int] = None,
    status_code: int = 200,
) -> None:
    """Log an UPDATE action"""
    activity_service = ActivityLogService(db)
    changes = get_changes(before, after)

    await activity_service.log_activity(
        organization_id=organization_id,
        user_id=user_id,
        action_type=ActionType.UPDATE,
        endpoint=str(request.url.path),
        method=request.method,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=changes,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status_code=status_code,
    )


async def log_delete(
    db: AsyncSession,
    request: Request,
    user_id: Optional[int],
    resource_type: str,
    resource_id: int,
    organization_id: Optional[int] = None,
    status_code: int = 204,
) -> None:
    """Log a DELETE action"""
    activity_service = ActivityLogService(db)
    metadata = {
        "message": f"{resource_type.capitalize()} deleted",
        "resource_id": resource_id,
    }

    await activity_service.log_activity(
        organization_id=organization_id,
        user_id=user_id,
        action_type=ActionType.DELETE,
        endpoint=str(request.url.path),
        method=request.method,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=metadata,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status_code=status_code,
    )


async def log_login(
    db: AsyncSession,
    request: Request,
    user_id: int,
    organization_id: Optional[int] = None,
    status_code: int = 200,
) -> None:
    """Log a LOGIN action"""
    activity_service = ActivityLogService(db)
    metadata = {
        "message": "User logged in successfully",
        "status": "success" if status_code == 200 else "failed",
    }

    await activity_service.log_activity(
        organization_id=organization_id,
        user_id=user_id,
        action_type=ActionType.LOGIN,
        endpoint=str(request.url.path),
        method=request.method,
        resource_type="auth",
        changes=metadata,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status_code=status_code,
    )


async def log_logout(
    db: AsyncSession,
    request: Request,
    user_id: int,
    organization_id: Optional[int] = None,
    status_code: int = 200,
) -> None:
    """Log a LOGOUT action"""
    activity_service = ActivityLogService(db)
    metadata = {"message": "User logged out"}

    await activity_service.log_activity(
        organization_id=organization_id,
        user_id=user_id,
        action_type=ActionType.LOGOUT,
        endpoint=str(request.url.path),
        method=request.method,
        resource_type="auth",
        changes=metadata,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
        status_code=status_code,
    )
