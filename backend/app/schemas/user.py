"""User and Authentication Pydantic schemas for validation"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from app.models.user import UserRole
from app.schemas.organization import OrganizationSummary


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: bool = True
    is_verified: bool = False
    role: UserRole = UserRole.USER
    mobile: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserCreate(UserBase):
    """Schema for creating or registering a new user"""
    password: str = Field(..., min_length=8, max_length=100)
    organization_id: Optional[int] = Field(
        None,
        description="Existing Organization ID to join",
    )
    organization_slug: Optional[str] = Field(
        None,
        description="Existing Organization slug to join (or new slug if organization_name is provided)",
    )
    organization_name: Optional[str] = Field(
        None,
        description="Optional: Create a new tenant organization during registration",
    )

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength"""
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class UserUpdate(BaseModel):
    """Schema for updating user profile or settings"""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    role: Optional[UserRole] = None
    mobile: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    organization_id: Optional[int] = None


class UserResponse(UserBase):
    """Schema for user response including tenant context"""
    id: int
    public_id: uuid.UUID
    organization_id: Optional[int] = None
    organization: Optional[OrganizationSummary] = None
    is_superuser: bool
    role: UserRole
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    """Schema for user in database (includes hashed password)"""
    hashed_password: str


# ── Authentication Schemas ───────────────────────────────────────────────────

class Token(BaseModel):
    """JWT Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")
    organization_id: Optional[int] = None
    user: Optional[UserResponse] = None


class TokenPayload(BaseModel):
    """Decoded JWT Token payload schema"""
    sub: Optional[str] = None
    org_id: Optional[int] = None
    role: Optional[str] = None
    jti: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    type: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str
    organization_slug: Optional[str] = Field(
        None,
        description="Optional organization slug to scope login",
    )


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str


class VerifyTokenRequest(BaseModel):
    """Verify token request schema"""
    token: str = Field(..., description="JWT access or refresh token to verify")
    token_type: str = Field("access", description="Expected token type: 'access' or 'refresh'")


class VerifyTokenResponse(BaseModel):
    """Verify token response schema"""
    valid: bool
    token_type: Optional[str] = None
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    role: Optional[str] = None
    expires_at: Optional[int] = None
    message: str


class ChangePasswordRequest(BaseModel):
    """Password change request for authenticated user"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class LogoutRequest(BaseModel):
    """Optional refresh token to revoke alongside current access token"""
    refresh_token: Optional[str] = None


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Generic paginated user response"""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[UserResponse]

    model_config = ConfigDict(from_attributes=True)
