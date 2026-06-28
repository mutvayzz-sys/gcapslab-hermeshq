from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from hermeshq.schemas.common import ORMModel
from hermeshq.schemas.user_management import _validate_password_strength


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AuthProviderRead(BaseModel):
    slug: str
    name: str
    kind: str
    enabled: bool = True


class AuthProvidersResponse(BaseModel):
    auth_mode: str
    local_login_enabled: bool
    oidc_enabled: bool
    providers: list[AuthProviderRead]


class UserRead(ORMModel):
    id: str
    username: str
    email: str | None = None
    display_name: str
    auth_source: str
    role: str
    is_active: bool
    theme_preference: str
    locale_preference: str
    avatar_url: str | None = None
    has_avatar: bool = False


class UserPreferencesUpdate(BaseModel):
    theme_preference: str | None = None
    locale_preference: str | None = None


class UserProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        _validate_password_strength(value)
        return value


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    new_password: str = Field(min_length=8, max_length=256)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        _validate_password_strength(value)
        return value


class PasswordResetResponse(BaseModel):
    message: str


class EmailConfigStatus(BaseModel):
    """Status of email configuration for the settings UI."""
    configured: bool = False
    from_email: str | None = None
    from_name: str | None = None
    public_base_url: str | None = None


class MfaRequiredResponse(BaseModel):
    """Response when login succeeds but MFA is required."""
    mfa_required: bool = True
    mfa_token: str
    email_mask: str | None = None
    expires_at: datetime


class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=2048)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaResendRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=2048)


class MfaStatusResponse(BaseModel):
    """MFA configuration status."""
    enabled: bool = False
    email_configured: bool = False


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(min_length=8, max_length=256)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        _validate_password_strength(value)
        return value


class RegisterResponse(BaseModel):
    message: str
    username: str
