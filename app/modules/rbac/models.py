from sqlalchemy import Boolean, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, generate_uuid


# ── Role Master ───────────────────────────────────────────────────────────────
class RoleMaster(Base):
    """
    Mirrors Java RoleMaster / role_master table.
    Defines named roles and which login methods are allowed.
    """

    __tablename__ = "role_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Login method gates
    pwd_login_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    mobile_otp_login_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    email_otp_login_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    social_login_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Module Master ─────────────────────────────────────────────────────────────
class ModuleMaster(Base):
    """
    Mirrors Java ModuleMaster / module_master table.
    Defines functional boundaries (e.g., USER_MANAGEMENT, INVENTORY).
    """

    __tablename__ = "module_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    module_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Role-Module Mapping (Global RBAC Matrix) ──────────────────────────────────
class RoleModuleMapping(Base):
    """
    Mirrors Java RoleModuleMapping / role_module_mapping table.
    Defines generic CRUD+Export privileges for a Role across a Module.
    """

    __tablename__ = "role_module_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    role_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("role_master.uuid", ondelete="CASCADE"), nullable=False
    )
    module_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("module_master.uuid", ondelete="CASCADE"), nullable=False
    )

    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)
    can_update: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Access Control Master (Per-User Override Matrix) ──────────────────────────
class AccessControlMaster(Base):
    """
    Mirrors Java AccessControlMaster / access_control_master table.
    Per-user overrides that take ABSOLUTE precedence over Role mappings.
    """

    __tablename__ = "access_control_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    user_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_login.uuid", ondelete="CASCADE"), nullable=False
    )
    module_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("module_master.uuid", ondelete="CASCADE"), nullable=False
    )

    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_write: Mapped[bool] = mapped_column(Boolean, default=False)
    can_update: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Refresh Token Store ───────────────────────────────────────────────────────
class RefreshToken(Base):
    """
    Persisted refresh tokens — enables server-side revocation.
    Mirrors the Java stateless JWT extension for refresh flow.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), default=generate_uuid, unique=True, index=True)
    user_uuid: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_login.uuid", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)  # ISO datetime string
