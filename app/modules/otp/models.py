from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OTPVerification(Base):
    """
    Database-backed OTP verification store.
    Identifier can be an email or phone number.
    OTP is stored as a hash for security.
    """
    __tablename__ = "otp_verifications"

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
    
    # Expiry and Verification - MySQL compatible datetime
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    
    # Attempt limiting
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
