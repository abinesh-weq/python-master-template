import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.otp.models import OTPVerification
from app.core.security import pwd_context
from app.core.config import settings

class OTPService:
    @staticmethod
    def generate_code() -> str:
        """Generate a secure 6-digit OTP."""
        return str(secrets.randbelow(900_000) + 100_000)

    async def get_verification(self, db: AsyncSession, identifier: str, otp_type: str) -> Optional[OTPVerification]:
        result = await db.execute(
            select(OTPVerification).where(
                OTPVerification.identifier == identifier.lower(),
                OTPVerification.otp_type == otp_type.upper()
            )
        )
        return result.scalar_one_or_none()

    async def send_otp(self, db: AsyncSession, identifier: str, otp_type: str, expire_minutes: int = 5) -> str:
        """
        Market Standard: Upsert OTP.
        If existing valid OTP exists, it will be replaced by a new one for security.
        """
        identifier = identifier.lower()
        otp_type = otp_type.upper()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # 1. Check existing
        existing = await self.get_verification(db, identifier, otp_type)
        
        # 2. Generate New
        otp_code = self.generate_code()
        otp_hash = pwd_context.hash(otp_code)
        expires_at = now + timedelta(minutes=expire_minutes)

        if existing:
            existing.otp_hash = otp_hash
            existing.expires_at = expires_at
            existing.attempt_count = 0
            existing.verified_at = None
        else:
            new_otp = OTPVerification(
                identifier=identifier,
                otp_type=otp_type,
                otp_hash=otp_hash,
                expires_at=expires_at,
                attempt_count=0
            )
            db.add(new_otp)
        
        await db.commit()
        return otp_code

    async def verify_otp(self, db: AsyncSession, identifier: str, otp_type: str, otp_code: str) -> bool:
        """
        Verifies OTP against hash. 
        Checks expiry and attempt limits.
        """
        identifier = identifier.lower()
        otp_type = otp_type.upper()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        otp_record = await self.get_verification(db, identifier, otp_type)
        if not otp_record:
            return False
            
        # 1. Check Expiry
        if now > otp_record.expires_at:
            return False
            
        # 2. Check Attempt Limits (Max 5)
        if otp_record.attempt_count >= 5:
            return False
            
        # 3. Verify Hash
        is_valid = pwd_context.verify(otp_code, otp_record.otp_hash)
        
        if is_valid:
            otp_record.verified_at = now
            otp_record.attempt_count = 0 # reset on success
        else:
            otp_record.attempt_count += 1
            
        await db.commit()
        return is_valid

    async def invalidate_otp(self, db: AsyncSession, identifier: str, otp_type: str):
        """Consume OTP after final use (registration)."""
        await db.execute(
            delete(OTPVerification).where(
                OTPVerification.identifier == identifier.lower(),
                OTPVerification.otp_type == otp_type.upper()
            )
        )
        await db.commit()

otp_service = OTPService()
