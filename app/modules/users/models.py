from typing import Optional
from sqlalchemy import Boolean, String
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.common_models.base_model import Base


class UserLogin(Base):
    """
    Mirrors Java UserLogin entity / user_login table.
    Central authentication identity record.
    """

    __tablename__ = "user_login"

    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=True)
    password: Mapped[str] = mapped_column(String(255), nullable=True)  # Nullable for SSO users

    # Auth provider — LOCAL | GOOGLE | APPLE | FACEBOOK
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="LOCAL"
    )

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # MFA / Biometric flags
    is_mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_biometric_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Device binding
    device_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # Role FK (single role per user — see rbac/models.py)
    role_uuid: Mapped[Optional[str]] = mapped_column(
        String(36), sa.ForeignKey("role_master.uuid", ondelete="SET NULL"), nullable=True
    )

    
