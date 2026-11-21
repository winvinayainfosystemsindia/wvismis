"""Shared API dependencies — JWT verification, token blacklist check, RBAC, and Multi-Tenancy resolution"""

from typing import Optional
from fastapi import Depends, HTTPException, Header, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token, verify_token_type
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.repositories.user_repository import UserRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.token_blacklist_repository import TokenBlacklistRepository


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token_query: Optional[str] = Query(None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT access token.
    Checks Authorization Bearer header first, then 'token' query parameter.
    Verifies signature, token type, blacklist revocation, and active user/organization status.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif token_query:
        token = token_query

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_token_type(payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if jti:
        blacklist_repo = TokenBlacklistRepository(db)
        if await blacklist_repo.is_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_repo = UserRepository(db)
    user = await user_repo.get(int(user_id))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    if user.organization and not user.organization.is_active and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Organization '{user.organization.name}' is inactive",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user"""
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require current user to be a superuser or SUPER_ADMIN"""
    if not current_user.is_superuser and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


async def get_current_organization(
    current_user: User = Depends(get_current_user),
    x_organization_id: Optional[int] = Header(None, alias="X-Organization-ID"),
    x_organization_slug: Optional[str] = Header(None, alias="X-Organization-Slug"),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """
    Resolve the active Organization (Tenant) for the request.
    - Regular users and ORG_ADMINs are strictly locked to their own organization_id.
    - Superusers / SUPER_ADMINs can optionally switch tenant context via X-Organization-ID or X-Organization-Slug headers.
    """
    org_repo = OrganizationRepository(db)
    is_super = current_user.is_superuser or current_user.role == UserRole.SUPER_ADMIN

    if x_organization_id is not None:
        if not is_super and x_organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access denied",
            )
        org = await org_repo.get(x_organization_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization {x_organization_id} not found",
            )
        return org

    if x_organization_slug is not None:
        org = await org_repo.get_by_slug(x_organization_slug)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization '{x_organization_slug}' not found",
            )
        if not is_super and org.id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access denied",
            )
        return org

    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not assigned to an organization",
        )

    org = await org_repo.get(current_user.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned organization not found",
        )
    return org


def require_roles(allowed_roles: list):
    """
    Create a dependency that checks if user has one of the allowed roles (or is a superuser).
    """

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser or current_user.role in (UserRole.SUPER_ADMIN, UserRole.OWNER):
            return current_user

        allowed_role_values = [
            role.value if isinstance(role, UserRole) else str(role)
            for role in allowed_roles
        ]
        # Admin equivalence: if admin is allowed, org_admin is also treated as admin
        if UserRole.ADMIN in allowed_roles or "admin" in allowed_role_values:
            allowed_role_values.extend([UserRole.ORG_ADMIN.value, "org_admin"])

        if current_user.role.value not in allowed_role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_role_values)}",
            )
        return current_user

    return role_checker
