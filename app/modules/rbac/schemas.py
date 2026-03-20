from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Role Schemas ──────────────────────────────────────────────────────────────
class RoleCreateRequest(BaseModel):
    name: str
    pwd_login_allowed: bool = True
    mobile_otp_login_allowed: bool = True
    email_otp_login_allowed: bool = True
    social_login_allowed: bool = False


class RoleResponse(BaseModel):
    id: str
    name: str
    pwd_login_allowed: bool
    mobile_otp_login_allowed: bool
    email_otp_login_allowed: bool
    social_login_allowed: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ── Module Schemas ────────────────────────────────────────────────────────────
class ModuleResponse(BaseModel):
    id: str
    module_code: str
    display_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ── Role-Module Mapping Schemas ───────────────────────────────────────────────
class PermissionToggleRequest(BaseModel):
    """Flat payload for toggling a single grid cell — PUT /roles/{roleUuid}/modules/{moduleUuid}"""

    can_read: Optional[bool] = None
    can_write: Optional[bool] = None
    can_update: Optional[bool] = None
    can_delete: Optional[bool] = None
    can_export: Optional[bool] = None


class RoleModuleMappingResponse(BaseModel):
    id: str
    role_id: str
    module_id: str
    can_read: bool
    can_write: bool
    can_update: bool
    can_delete: bool
    can_export: bool

    model_config = ConfigDict(from_attributes=True)


# ── Access Control (User Override) Schemas ────────────────────────────────────
class AccessControlResponse(BaseModel):
    id: str
    user_id: str
    module_id: str
    can_read: bool
    can_write: bool
    can_update: bool
    can_delete: bool
    can_export: bool

    model_config = ConfigDict(from_attributes=True)
