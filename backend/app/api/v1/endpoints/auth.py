"""Authentication endpoints — Register, Login, Verify Token, Refresh Token, Logout, Change Password, Me"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_action_token,
    decode_token,
    verify_token_type,
    get_password_hash,
)
from app.core.rate_limiter import rate_limit_auth, rate_limit_medium
from app.schemas.user import (
    UserCreate,
    UserResponse,
    Token,
    LoginRequest,
    RefreshTokenRequest,
    VerifyTokenRequest,
    VerifyTokenResponse,
    ChangePasswordRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    AcceptInviteRequest,
)
from app.services.user_service import UserService
from app.repositories.token_blacklist_repository import TokenBlacklistRepository
from app.utils.activity_tracker import log_create, log_login, log_logout, log_update
from app.utils.email import send_email, render_template
from app.api.deps import get_current_user, security
from app.models.user import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (with multi-tenant organization assignment)",
)
@rate_limit_auth()
async def register(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    - **email**: Valid unique email address
    - **username**: Unique username (3-100 characters)
    - **password**: Strong password (min 8 chars, uppercase, lowercase, digit)
    - **organization_id** / **organization_slug**: Join an existing tenant organization
    - **organization_name**: Optional — create a new tenant organization and become its `org_admin`
    """
    logger.info(f"New user registration attempt: {user_in.email}")

    user_service = UserService(db)
    user = await user_service.create_user(user_in)

    await log_create(
        db=db,
        request=request,
        organization_id=user.organization_id,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        created_object=user,
        status_code=201,
    )

    logger.info(f"User registered successfully: {user.email} (org_id={user.organization_id})")
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login and receive JWT access and refresh tokens",
)
@rate_limit_auth()
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email, password, and optional `organization_slug`.
    Returns signed JWT `access_token`, `refresh_token`, expiration metadata, and user profile.
    """
    login_identifier = (login_data.identifier or login_data.email or "").strip()
    logger.info(f"Login attempt for: {login_identifier}")

    user_service = UserService(db)
    user = await user_service.authenticate(
        email=login_identifier,
        password=login_data.password,
        organization_slug=login_data.organization_slug,
    )

    if not user:
        logger.warning(f"Failed login attempt for: {login_identifier}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_response = UserResponse.model_validate(user)

    token_claims = {
        "sub": str(user.id),
        "org_id": user.organization_id,
        "role": user.role.value,
    }

    access_token = create_access_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    refresh_token = create_refresh_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )

    await log_login(
        db=db,
        request=request,
        organization_id=user.organization_id,
        user_id=user.id,
    )

    logger.info(f"User logged in successfully: {user.email}")

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        organization_id=user.organization_id,
        user=user_response,
    )


@router.post(
    "/verify",
    response_model=VerifyTokenResponse,
    summary="Verify a JWT access or refresh token",
)
@rate_limit_medium()
async def verify_token(
    request: Request,
    verify_data: VerifyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate a JWT token signature, expiration, token type (`access` or `refresh`),
    revocation blacklist status, and underlying user active state.
    """
    payload = decode_token(verify_data.token)
    if payload is None:
        return VerifyTokenResponse(
            valid=False,
            message="Token is invalid or expired",
        )

    actual_type = payload.get("type")
    if verify_data.token_type and actual_type != verify_data.token_type:
        return VerifyTokenResponse(
            valid=False,
            token_type=actual_type,
            message=f"Expected token type '{verify_data.token_type}', got '{actual_type}'",
        )

    jti = payload.get("jti")
    if jti:
        blacklist_repo = TokenBlacklistRepository(db)
        if await blacklist_repo.is_blacklisted(jti):
            return VerifyTokenResponse(
                valid=False,
                token_type=actual_type,
                message="Token has been revoked",
            )

    sub = payload.get("sub")
    if not sub:
        return VerifyTokenResponse(
            valid=False,
            token_type=actual_type,
            message="Token missing subject claim",
        )

    user_service = UserService(db)
    try:
        user = await user_service.get_user(int(sub))
    except HTTPException:
        return VerifyTokenResponse(
            valid=False,
            token_type=actual_type,
            message="User associated with token no longer exists",
        )

    if not user.is_active:
        return VerifyTokenResponse(
            valid=False,
            token_type=actual_type,
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role.value,
            message="User account is inactive",
        )

    return VerifyTokenResponse(
        valid=True,
        token_type=actual_type,
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role.value,
        expires_at=payload.get("exp"),
        message="Token is valid",
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Rotate and refresh JWT access token using refresh token",
)
@rate_limit_auth()
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using a valid refresh token.
    Revokes the old refresh token JTI (rotation) and issues a new token pair.
    """
    payload = decode_token(refresh_data.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_token_type(payload, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    blacklist_repo = TokenBlacklistRepository(db)
    old_jti = payload.get("jti")
    if old_jti and await blacklist_repo.is_blacklisted(old_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has already been used or revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user_service = UserService(db)
    user = await user_service.get_user(int(user_id))

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    user_response = UserResponse.model_validate(user)

    # Rotate old refresh token by blacklisting its JTI
    if old_jti:
        exp_ts = payload.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            if exp_ts
            else datetime.now(timezone.utc) + timedelta(days=7)
        )
        await blacklist_repo.blacklist_token(
            jti=old_jti,
            token_type="refresh",
            expires_at=expires_at,
            user_id=user.id,
            reason="refresh_rotation",
        )

    token_claims = {
        "sub": str(user.id),
        "org_id": user.organization_id,
        "role": user.role.value,
    }

    new_access_token = create_access_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    new_refresh_token = create_refresh_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )

    logger.info(f"Token refreshed for user: {user.email}")

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        organization_id=user.organization_id,
        user=user_response,
    )


@router.post(
    "/logout",
    summary="Logout and revoke current access and refresh tokens",
)
async def logout(
    request: Request,
    logout_data: Optional[LogoutRequest] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke the caller's active JWT access token (and optional refresh token) so they cannot be reused.
    """
    blacklist_repo = TokenBlacklistRepository(db)

    if credentials and credentials.credentials:
        access_payload = decode_token(credentials.credentials)
        if access_payload and access_payload.get("jti"):
            exp_ts = access_payload.get("exp")
            expires_at = (
                datetime.fromtimestamp(exp_ts, tz=timezone.utc)
                if exp_ts
                else datetime.now(timezone.utc) + timedelta(hours=1)
            )
            await blacklist_repo.blacklist_token(
                jti=access_payload["jti"],
                token_type="access",
                expires_at=expires_at,
                user_id=current_user.id,
                reason="logout",
            )

    if logout_data and logout_data.refresh_token:
        refresh_payload = decode_token(logout_data.refresh_token)
        if refresh_payload and refresh_payload.get("jti"):
            exp_ts = refresh_payload.get("exp")
            expires_at = (
                datetime.fromtimestamp(exp_ts, tz=timezone.utc)
                if exp_ts
                else datetime.now(timezone.utc) + timedelta(days=7)
            )
            await blacklist_repo.blacklist_token(
                jti=refresh_payload["jti"],
                token_type="refresh",
                expires_at=expires_at,
                user_id=current_user.id,
                reason="logout",
            )

    await log_logout(
        db=db,
        request=request,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
    )

    return {"message": "Successfully logged out and revoked token(s)"}


@router.post(
    "/change-password",
    summary="Change password for the currently authenticated user",
)
@rate_limit_auth()
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify current password and update to a new strong password."""
    user_service = UserService(db)
    await user_service.change_password(
        user=current_user,
        current_password=password_data.current_password,
        new_password=password_data.new_password,
    )

    await log_update(
        db=db,
        request=request,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        before={"password": "old"},
        after={"password": "changed"},
    )
    return {"message": "Password updated successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get currently authenticated user profile and tenant context",
)
async def get_authenticated_me(
    current_user: User = Depends(get_current_user),
):
    """Returns the authenticated user's profile and embedded Organization summary."""
    return current_user


@router.post(
    "/forgot-password",
    summary="Request a password reset link sent to email",
)
@rate_limit_auth()
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a 1-hour password reset token and dispatch an email to the user.
    Always returns a 200 OK generic message to prevent email enumeration.
    """
    email_clean = payload.email.strip().lower()
    logger.info(f"Password reset requested for: {email_clean}")

    user_service = UserService(db)
    user = await user_service.repository.get_by_email(email_clean)

    if user and not user.is_deleted:
        reset_token = create_action_token(
            data={"sub": str(user.id), "email": user.email},
            action_type="password_reset",
            expires_delta=timedelta(hours=1),
        )
        origin = request.headers.get("origin") or getattr(settings, "FRONTEND_URL", None) or "https://dev-mis.winvinaya.com"
        reset_url = f"{origin.rstrip('/')}/auth/reset-password?token={reset_token}"

        html_content = render_template(
            "password_reset.html",
            {
                "user_name": user.full_name or user.username,
                "user_email": user.email,
                "reset_url": reset_url,
            },
        )
        try:
            await send_email(
                to_email=user.email,
                subject="Reset Your Password - WinVinaya MIS",
                html_content=html_content,
            )
        except Exception as exc:
            logger.error(f"Failed to send password reset email to {user.email}: {exc}")

    return {
        "message": "If an account exists with this email address, a password reset link has been sent to your inbox."
    }


@router.post(
    "/reset-password",
    summary="Reset password using a valid action token",
)
@rate_limit_auth()
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify password reset token and apply new password."""
    token_payload = decode_token(payload.token)
    if not token_payload or token_payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or malformed password reset token.",
        )

    user_id_str = token_payload.get("sub")
    email_str = token_payload.get("email")

    user_service = UserService(db)
    user = None
    if user_id_str and str(user_id_str).isdigit():
        user = await user_service.repository.get(int(user_id_str))
    elif email_str:
        user = await user_service.repository.get_by_email(email_str)

    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account associated with this token no longer exists.",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    await db.commit()

    await log_update(
        db=db,
        request=request,
        organization_id=user.organization_id,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        before={"password": "old"},
        after={"password": "reset_via_token"},
    )

    return {"message": "Password updated successfully. You may now log in with your new password."}


@router.post(
    "/accept-invite",
    response_model=Token,
    summary="Accept team invitation, set password, and auto-login",
)
@rate_limit_auth()
async def accept_invite(
    request: Request,
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify 7-day invite action token, activate and verify user account,
    store strong password, and return JWT credentials for immediate login.
    """
    token_payload = decode_token(payload.token)
    if not token_payload or token_payload.get("type") != "invite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or malformed invitation link.",
        )

    user_id_str = token_payload.get("sub")
    email_str = token_payload.get("email")

    user_service = UserService(db)
    user = None
    if user_id_str and str(user_id_str).isdigit():
        user = await user_service.repository.get(int(user_id_str))
    elif email_str:
        user = await user_service.repository.get_by_email(email_str)

    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The invited user account was not found or has been revoked.",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    user.is_verified = True
    user.is_active = True
    await db.commit()
    await db.refresh(user)

    user_response = UserResponse.model_validate(user)
    token_claims = {
        "sub": str(user.id),
        "org_id": user.organization_id,
        "role": user.role.value,
    }
    access_token = create_access_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        data=token_claims,
        expires_delta=timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES),
    )

    await log_login(
        db=db,
        request=request,
        organization_id=user.organization_id,
        user_id=user.id,
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        organization_id=user.organization_id,
        user=user_response,
    )
