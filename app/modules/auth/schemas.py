import re
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.core.config import settings


# ── Registration ──────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str
    email_otp: Optional[str] = None  # Required for /register (public)
    mobile_otp: Optional[str] = None  # Required for /register (public)
    role_name: Optional[str] = None  # Used by /admin/register only

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.match(settings.PASSWORD_REGEX, v):
            raise ValueError(
                "Password does not meet complexity requirements. "
                "Must be 8+ characters, include upper, lower, digit, and special char."
            )
        return v

    @model_validator(mode="after")
    def validate_contacts_and_otps(self):
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided.")
        if self.email and not self.email_otp:
            raise ValueError("email_otp is required when email is provided.")
        if self.phone_number and not self.mobile_otp:
            raise ValueError("mobile_otp is required when phone_number is provided.")
        return self


# ── Password Login ────────────────────────────────────────────────────────────
class PasswordLoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_id: Optional[str] = None


# ── MFA Login ─────────────────────────────────────────────────────────────────
class MfaLoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_otp: str


# ── OTP Login ─────────────────────────────────────────────────────────────────
class OtpLoginRequest(BaseModel):
    identifier: str  # email or phone_number depending on endpoint
    otp: str


# ── Social / SSO Login ────────────────────────────────────────────────────────
class SocialLoginRequest(BaseModel):
    access_token: str  # Token from provider
    provider: str  # GOOGLE | FACEBOOK | APPLE
    device_id: Optional[str] = None


# ── OTP Send / Verify ─────────────────────────────────────────────────────────
class SendOtpRequest(BaseModel):
    identifier: str  # email or phone_number
    otp_type: str  # EMAIL_OTP | MOBILE_OTP | MFA


class VerifyOtpRequest(BaseModel):
    identifier: str
    otp_type: str
    otp: str


# ── Password Reset ────────────────────────────────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_otp: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.match(settings.PASSWORD_REGEX, v):
            raise ValueError(
                "Password does not meet complexity requirements. "
                "Must be 8+ characters, include upper, lower, digit, and special char."
            )
        return v


# ── Token Refresh ─────────────────────────────────────────────────────────────
class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ── Responses ─────────────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class MfaPendingResponse(BaseModel):
    mfa_required: bool = True
    message: str = "MFA OTP has been sent. Please complete MFA login."
