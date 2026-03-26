import re
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, PrivateAttr, field_validator, model_validator

from app.core.config import settings


# ── Registration ──────────────────────────────────────────────────────────────
class BaseRegisterRequest(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str
    role_name: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(settings.USERNAME_REGEX, v):
            raise ValueError(
                "Username must be 3-30 characters and contain only letters, digits, '_', '-', or '.'."
            )
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(settings.PHONE_NUMBER_REGEX, v):
            raise ValueError("Phone number must contain 7-15 digits only.")
        return v

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
    def validate_contacts(self):
        if not self.email and not self.phone_number:
            raise ValueError("Either email or phone_number must be provided.")
        return self


class RegisterRequest(BaseRegisterRequest):
    email_otp: Optional[str] = None  # Required for /register (public)
    mobile_otp: Optional[str] = None  # Required for /register (public)

    @model_validator(mode="after")
    def validate_otps(self):
        if self.email and not self.email_otp:
            raise ValueError("email_otp is required when email is provided.")
        if self.phone_number and not self.mobile_otp:
            raise ValueError("mobile_otp is required when phone_number is provided.")
        return self


class AdminRegisterRequest(BaseRegisterRequest):
    pass


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


# ── OTP Login (unified smart identifier) ─────────────────────────────────────

# Compiled once at module load for performance
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.[a-zA-Z]{2,}$"
)
# Strips everything except leading + and digits, then validates length
_PHONE_STRIP_RE = re.compile(r"[\s\-().]")  # characters to strip before check

# Shared validation messages
_ERR_IDENTIFIER_EMPTY = "identifier must be a non-empty string."
_ERR_PASSWORD_COMPLEXITY = (
    "Password does not meet complexity requirements. "
    "Must be 8+ characters, include upper, lower, digit, and special char."
)


def _detect_and_normalise(raw: str) -> tuple[Literal["email", "mobile"], str]:
    """
    Returns (identifier_type, normalised_value).
    Email is checked first — @ is unambiguous.
    Phone accepts:
        +919876543210   (E.164 with country code)
        919876543210    (country code, no +)
        9876543210      (local, 10 digits)
        +1 (800) 555-1234  (formatted US number)
        0044 7911 123456   (UK with leading 00)
    All stripped to pure digits, then re-prefixed with + for storage.
    """
    v = raw.strip()

    # ── Email detection ───────────────────────────────────────────────────────
    if "@" in v:
        if not _EMAIL_RE.match(v):
            raise ValueError(
                "Looks like an email but has an invalid format. "
                "Expected: user@domain.tld"
            )
        return "email", v.lower()

    # ── Phone detection ───────────────────────────────────────────────────────
    # Preserve an optional leading +, then strip formatting chars
    has_plus = v.startswith("+")
    digits_only = _PHONE_STRIP_RE.sub("", v.lstrip("+"))

    # Handle 00-prefix (international dialling prefix used in some countries)
    if digits_only.startswith("00"):
        digits_only = digits_only[2:]  # strip 00 → treat as country-code digits
        has_plus = True

    if not digits_only.isdigit():
        raise ValueError(
            "Identifier is not a valid email (missing '@') and not a valid phone number "
            "(contains non-digit characters after stripping formatting)."
        )

    # E.164 limits: 7 (shortest local) to 15 digits (incl. country code)
    if not (7 <= len(digits_only) <= 15):
        raise ValueError(
            f"Phone number must be 7–15 digits (after stripping formatting); "
            f"got {len(digits_only)}."
        )

    normalised = f"+{digits_only}" if has_plus else digits_only
    return "mobile", normalised


class OtpLoginRequest(BaseModel):
    """
    Unified OTP login request.
    Pass either an email address or a phone number as `identifier`.
    The API auto-detects the type and routes accordingly.

    Accepted phone formats:
      • +919876543210   (E.164)
      • 919876543210   (no leading +)
      • 9876543210      (10-digit local)
      • +1 (800) 555-1234
      • 0044 7911 123456
    """

    identifier: str
    otp: str

    # Internal only — never serialised, never shown in Swagger
    _identifier_type: Literal["email", "mobile"] = PrivateAttr(default="email")

    @model_validator(mode="after")
    def detect_and_normalise_identifier(self) -> "OtpLoginRequest":
        if not self.identifier or not self.identifier.strip():
            raise ValueError("identifier must be a non-empty string.")

        id_type, normalised = _detect_and_normalise(self.identifier)
        self.identifier = normalised
        self._identifier_type = id_type
        return self

    @property
    def identifier_type(self) -> Literal["email", "mobile"]:
        """Resolved identifier type — email or mobile. Read-only, internal use only."""
        return self._identifier_type


# ── Social / SSO Login ────────────────────────────────────────────────────────
class SocialLoginRequest(BaseModel):
    access_token: str  # Token from provider
    provider: str  # GOOGLE | FACEBOOK | APPLE
    device_id: Optional[str] = None


# ── OTP Send / Verify ─────────────────────────────────────────────────────────

def _identifier_to_otp_type(id_type: Literal["email", "mobile"]) -> str:
    """Maps detected identifier type to the OTP type string used internally."""
    return "EMAIL_OTP" if id_type == "email" else "MOBILE_OTP"


class SendOtpRequest(BaseModel):
    """
    Send OTP request.
    Pass an email or phone number as `identifier` — type is auto-detected.
    """

    identifier: str

    _otp_type: str = PrivateAttr(default="EMAIL_OTP")

    @model_validator(mode="after")
    def detect_identifier(self) -> "SendOtpRequest":
        if not self.identifier or not self.identifier.strip():
            raise ValueError("identifier must be a non-empty string.")
        id_type, normalised = _detect_and_normalise(self.identifier)
        self.identifier = normalised
        self._otp_type = _identifier_to_otp_type(id_type)
        return self

    @property
    def otp_type(self) -> str:
        """Resolved OTP type — EMAIL_OTP or MOBILE_OTP. Internal use only."""
        return self._otp_type


class VerifyOtpRequest(BaseModel):
    """
    Verify OTP request.
    Pass an email or phone number as `identifier` — type is auto-detected.
    """

    identifier: str
    otp: str

    _otp_type: str = PrivateAttr(default="EMAIL_OTP")

    @model_validator(mode="after")
    def detect_identifier(self) -> "VerifyOtpRequest":
        if not self.identifier or not self.identifier.strip():
            raise ValueError("identifier must be a non-empty string.")
        id_type, normalised = _detect_and_normalise(self.identifier)
        self.identifier = normalised
        self._otp_type = _identifier_to_otp_type(id_type)
        return self

    @property
    def otp_type(self) -> str:
        """Resolved OTP type — EMAIL_OTP or MOBILE_OTP. Internal use only."""
        return self._otp_type


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
class ChangePasswordRequest(BaseModel):
    old_password: str
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


class RegisterResponse(BaseModel):
    id: int
    email: Optional[EmailStr] = None
