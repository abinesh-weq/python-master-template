import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.config import settings


class UserBase(BaseModel):
    name: Optional[str] = None
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    provider: str = "LOCAL"
    is_active: bool = True
    is_verified: bool = False

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(settings.USERNAME_REGEX, v):
            raise ValueError(
                "Username must be 3-30 characters and contain only letters, digits, '_', '-', or '.'."
            )
        return v

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_and_validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not isinstance(v, str):
            raise ValueError("Phone number must be a string.")

        # trim and normalize
        normalized = re.sub(r"[\s\-\(\)]", "", v)
        if normalized.startswith("+"):
            normalized = normalized[1:]

        if not normalized.isdigit():
            raise ValueError("Phone number must contain only digits after normalization.")

        if len(normalized) < 10 or len(normalized) > 15:
            raise ValueError("Phone number length must be between 10 and 15 digits.")

        # Prefer E.164-style storage
        return f"+{normalized}"
    is_mfa_enabled: bool = False
    is_biometric_enabled: bool = False
    device_id: Optional[str] = None
    role_uuid: Optional[str] = None


class UserCreateRequest(UserBase):
    password: Optional[str] = None


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    is_mfa_enabled: Optional[bool] = None
    is_biometric_enabled: Optional[bool] = None
    device_id: Optional[str] = None
    role_uuid: Optional[str] = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str


class UserResponse(UserBase):
    id: int
    uuid: str

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    id: int
    uuid: str
    username: str
    email: str
    phone_number: Optional[str] = None
    provider: str
    is_active: bool
    role_uuid: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
