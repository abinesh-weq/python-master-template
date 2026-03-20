from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, generate_uuid


class UserLogin(Base):
    """
    Mirrors Java UserLogin entity / user_login table.
    Central authentication identity record.
    """

    __tablename__ = "user_login"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
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
    role_id: Mapped[str] = mapped_column(String(36), nullable=True)

    # Standard Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
