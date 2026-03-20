from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    name: Optional[str] = None
    username: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    provider: str = "LOCAL"
    is_active: bool = True
    is_verified: bool = False
    is_mfa_enabled: bool = False
    is_biometric_enabled: bool = False
    device_id: Optional[str] = None
    role_id: Optional[str] = None


class UserCreateRequest(UserBase):
    password: Optional[str] = None


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    is_mfa_enabled: Optional[bool] = None
    is_biometric_enabled: Optional[bool] = None
    device_id: Optional[str] = None
    role_id: Optional[str] = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str


class UserResponse(UserBase):
    id: str

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    id: str
    username: str
    email: str
    phone_number: Optional[str] = None
    provider: str
    is_active: bool
    role_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
