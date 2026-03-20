from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, generate_uuid


class OTPVerification(Base):
    """
    Database-backed OTP verification store.
    Identifier can be an email or phone number.
    OTP is stored as a hash for security.
    """
    __tablename__ = "otp_verifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    identifier: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    otp_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DEFAULT", index=True
    )
    otp_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("identifier", "otp_type", name="uq_otp_identifier_type"),
    )
    
    # Expiry and Verification
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Attempt limiting
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
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
